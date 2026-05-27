import json
import re
import warnings
from pathlib import Path
from bs4 import BeautifulSoup, Tag, NavigableString, XMLParsedAsHTMLWarning
from openai import OpenAI
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

console = Console()

BATCH_DELIMITER = "\n\n---TRANSLATION_SEPARATOR---\n\n"

# Elements that contain text worth translating
TEXT_ELEMENTS = {
    "p", "h1", "h2", "h3", "h4", "h5", "h6",
    "li", "blockquote", "figcaption", "dt", "dd",
    "td", "th", "caption", "summary", "legend",
}


def translate_html_dir(
    html_dir: str | Path,
    config: dict,
    progress_file: str | Path = "temp/progress.json",
    metadata_file: str | Path = "temp/metadata.json",
) -> None:
    """Translate HTML files from the spine, modifying them in-place with bilingual content."""
    html_dir = Path(html_dir)
    progress_path = Path(progress_file)
    metadata_path = Path(metadata_file)

    # Read metadata to get ordered docs (spine documents only)
    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    doc_names = {d["file_name"] for d in metadata.get("ordered_docs", [])}
    html_files = sorted(
        [f for f in html_dir.glob("*.xhtml") if f.name in doc_names]
        + [f for f in html_dir.glob("*.html") if f.name in doc_names]
    )

    if not html_files:
        console.print("[yellow]No spine HTML files found to translate.[/]")
        return

    # Load progress (set of already-translated filenames)
    output_mode = config.get("output_mode", "bilingual")
    completed = _load_progress(progress_path, output_mode)

    # Filter out already completed files
    remaining = [f for f in html_files if f.name not in completed]
    if not remaining:
        console.print("[green]All files already translated.[/]")
        return

    console.print(f"[bold]Translating:[/] {len(remaining)} files "
                  f"(skipping {len(completed)} already done)")

    client = OpenAI(
        api_key=config["api_key"],
        base_url="https://api.deepseek.com/v1",
    )

    code_selectors = config.get("code_selectors", ["pre", "code"])

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
    ) as progress:
        file_task = progress.add_task("[cyan]Files", total=len(remaining))

        for html_file in remaining:
            progress.update(file_task, description=f"[cyan]{html_file.name}")

            try:
                _translate_file(html_file, client, config, code_selectors, progress)
                completed.add(html_file.name)
                _save_progress(progress_path, completed, output_mode)
            except Exception as e:
                console.print(f"[red]Error translating {html_file.name}: {e}[/]")
                # Save progress anyway so completed files are preserved
                _save_progress(progress_path, completed, output_mode)
                raise

            progress.advance(file_task)

    console.print(f"[green]HTML translation complete:[/] {len(completed)} files")

    # Translate TOC titles in metadata
    if metadata.get("toc"):
        console.print("[bold]Translating TOC titles...[/]")
        _translate_toc_metadata(metadata, client, config, metadata_path)


def _translate_file(
    filepath: Path,
    client: OpenAI,
    config: dict,
    code_selectors: list[str],
    progress: Progress,
) -> None:
    with open(filepath, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "lxml")

    # Build CSS selector to skip code elements
    skip_selector = ", ".join(code_selectors)

    # Collect all translatable paragraphs
    paragraphs: list[Tag] = []
    for element in soup.select(", ".join(TEXT_ELEMENTS)):
        if element.parent and _is_inside_code(element, code_selectors):
            continue
        text = _get_direct_text(element)
        if text and len(text.strip()) > 1:
            paragraphs.append(element)

    if not paragraphs:
        console.print(f"  [dim]No translatable content in {filepath.name}[/]")
        return

    # Build batch of texts to translate
    texts = [_get_direct_text(p) for p in paragraphs]
    translations = _batch_translate(client, config, texts, progress)

    output_mode = config.get("output_mode", "bilingual")

    if output_mode == "chinese_only":
        # Replace original text with translation
        for para, translation in zip(paragraphs, translations):
            if translation and translation.strip():
                para.string = translation.strip()
        # Remove any existing trans-bilingual elements from prior runs
        for tag in soup.find_all(class_="trans-bilingual"):
            tag.decompose()
        # Remove bilingual styles
        existing_style = soup.find("style", id="trans-bilingual-style")
        if existing_style:
            existing_style.decompose()
    else:
        # Insert translation paragraphs after originals (bilingual mode)
        for para, translation in zip(paragraphs, translations):
            if translation and translation.strip():
                trans_tag = soup.new_tag(para.name)
                trans_tag["class"] = "trans-bilingual"
                trans_tag.string = translation.strip()
                para.insert_after(trans_tag)
        # Inject style
        _inject_styles(soup)

    # Write back
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(str(soup))


def _get_direct_text(element: Tag) -> str:
    """Get the direct text content of an element, excluding nested code blocks."""
    parts = []
    for child in element.children:
        if isinstance(child, NavigableString):
            parts.append(str(child))
        elif isinstance(child, Tag):
            if child.name in ("pre", "code"):
                continue
            parts.append(child.get_text())
    return "".join(parts).strip()


def _is_inside_code(element: Tag, code_selectors: list[str]) -> bool:
    """Check if an element is inside a code block."""
    for parent in element.parents:
        for selector in code_selectors:
            if parent.name == selector:
                return True

    if element.name in code_selectors:
        return True
    return False


def _batch_translate(
    client: OpenAI,
    config: dict,
    texts: list[str],
    progress: Progress,
    batch_size: int = 10,
) -> list[str]:
    """Translate texts in batches for efficiency. Returns list of translations in same order."""
    all_translations = []

    total_batches = (len(texts) + batch_size - 1) // batch_size
    batch_task = progress.add_task(
        f"  [dim]Paragraphs ({len(texts)} total)",
        total=total_batches,
        transient=True,
    )

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        numbered = "\n".join(f"[{j}] {t}" for j, t in enumerate(batch))

        system_prompt = (
            "You are a precise English-to-Chinese translator. "
            "Translate each paragraph below into natural, fluent Chinese. "
            f"Output translations separated by the delimiter '{BATCH_DELIMITER}'. "
            "Maintain technical term accuracy. Output ONLY the translations, no explanations. "
            "Preserve the numbering format [N] before each translation."
        )

        response = client.chat.completions.create(
            model=config["model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": numbered},
            ],
            temperature=config.get("temperature", 0.3),
            max_tokens=config.get("max_tokens", 2000),
        )

        result = response.choices[0].message.content or ""

        # Parse batch result
        parts = result.split(BATCH_DELIMITER)
        if len(parts) != len(batch):
            # If delimiter parsing fails, try to split by [N] pattern
            parts = _fallback_parse(result, len(batch))

        # Extend to match batch size
        while len(parts) < len(batch):
            parts.append("")

        parts = [_clean_delimiter(p) for p in parts]
        all_translations.extend(parts[:len(batch)])
        progress.advance(batch_task)

    progress.remove_task(batch_task)
    return all_translations


def _fallback_parse(result: str, expected_count: int) -> list[str]:
    """Fallback: try to split by [N] numbering pattern."""
    # Strip the leading [N] from each line
    lines = result.strip().split("\n")
    translations = []
    current = []
    for line in lines:
        if re.match(r'^\[\d+\]', line):
            if current:
                translations.append(" ".join(current))
                current = []
            # Remove the [N] prefix
            cleaned = re.sub(r'^\[\d+\]\s*', '', line)
            current.append(cleaned)
        else:
            current.append(line)
    if current:
        translations.append(" ".join(current))

    while len(translations) < expected_count:
        translations.append("")
    return translations


def _translate_toc_metadata(metadata: dict, client: OpenAI, config: dict, metadata_path: Path) -> None:
    """Translate all TOC titles in-place and save metadata back to disk."""
    # Flatten TOC: collect (path, title) pairs
    entries = []

    def collect(entry_list: list, path_prefix: list):
        for i, entry in enumerate(entry_list):
            entry_path = path_prefix + [i]
            entries.append((entry_path, entry["title"]))
            if "children" in entry and entry["children"]:
                collect(entry["children"], entry_path)

    collect(metadata["toc"], [])

    if not entries:
        return

    titles = [title for _, title in entries]
    translations = _batch_translate_titles(client, config, titles)

    # Apply titles based on output mode
    output_mode = config.get("output_mode", "bilingual")
    for (entry_path, original_title), translated in zip(entries, translations):
        if translated and translated.strip():
            target = metadata["toc"]
            for idx in entry_path[:-1]:
                target = target[idx].get("children", target[idx])
            if output_mode == "chinese_only":
                target[entry_path[-1]]["title"] = translated.strip()
            else:
                target[entry_path[-1]]["title"] = f"{original_title} / {translated.strip()}"

    # Save updated metadata
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    console.print(f"[green]TOC titles translated:[/] {len(titles)}")


def _batch_translate_titles(client: OpenAI, config: dict, titles: list[str], batch_size: int = 20) -> list[str]:
    """Translate TOC titles (chapter/section names) in batches."""
    all_translations = []

    for i in range(0, len(titles), batch_size):
        batch = titles[i:i + batch_size]
        numbered = "\n".join(f"[{j}] {t}" for j, t in enumerate(batch))

        system_prompt = (
            "You are a precise English-to-Chinese translator. "
            "Translate each book chapter/section title below into natural Chinese. "
            "These are book table-of-contents entries — keep them concise and book-style. "
            f"Output translations separated by the delimiter '{BATCH_DELIMITER}'. "
            "Output ONLY the translations, no explanations. "
            "Preserve the numbering format [N] before each translation."
        )

        response = client.chat.completions.create(
            model=config["model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": numbered},
            ],
            temperature=config.get("temperature", 0.3),
            max_tokens=config.get("max_tokens", 2000),
        )

        result = response.choices[0].message.content or ""
        parts = result.split(BATCH_DELIMITER)
        if len(parts) != len(batch):
            parts = _fallback_parse(result, len(batch))
        while len(parts) < len(batch):
            parts.append("")
        parts = [_clean_delimiter(p) for p in parts]
        all_translations.extend(parts[:len(batch)])

    return all_translations


def _inject_styles(soup: BeautifulSoup) -> None:
    """Add bilingual translation styles to the HTML head."""
    head = soup.find("head")
    if not head:
        head = soup.new_tag("head")
        html_tag = soup.find("html")
        if html_tag:
            html_tag.insert(0, head)
        else:
            soup.insert(0, head)

    existing = head.find("style", id="trans-bilingual-style")
    if existing:
        return  # Already injected

    style = soup.new_tag("style")
    style["id"] = "trans-bilingual-style"
    style.string = """
        .trans-bilingual {
            color: #556B2F;
            font-style: italic;
            background-color: #F5F5F5;
            margin-top: 0.2em;
            margin-bottom: 1em;
            padding: 0.3em 0.5em;
            border-left: 3px solid #8FBC8F;
            border-radius: 0 4px 4px 0;
        }
    """
    head.append(style)


def _clean_delimiter(text: str) -> str:
    """Remove any leftover BATCH_DELIMITER fragments from a translation."""
    import re
    # Match patterns like "---TRANSLATION_SEPARATOR---" with optional spaces
    text = re.sub(r'-{2,}\s*TRANSLATION[-_\s]*SEPARATOR\s*-{2,}', '', text)
    return text.strip()


def _load_progress(progress_path: Path, output_mode: str) -> set:
    """Load the set of completed filenames. Returns empty set if output_mode changed."""
    if not progress_path.exists():
        return set()
    try:
        with open(progress_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if data.get("output_mode") != output_mode:
                return set()
            return set(data.get("completed", []))
    except (json.JSONDecodeError, KeyError):
        return set()


def _save_progress(progress_path: Path, completed: set, output_mode: str) -> None:
    """Save the set of completed filenames with output_mode."""
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    with open(progress_path, "w", encoding="utf-8") as f:
        json.dump({"completed": list(completed), "output_mode": output_mode},
                  f, ensure_ascii=False)
