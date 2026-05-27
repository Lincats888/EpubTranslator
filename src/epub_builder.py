import json
import re
import shutil
from pathlib import Path
from ebooklib import epub
from rich.console import Console

console = Console()


def build_epub(temp_dir: str | Path = "temp", output_dir: str | Path = "output",
               cleanup: bool = False) -> str:
    """Rebuild EPUB from translated HTML and resources, output bilingual EPUB.

    Set cleanup=True to remove temp directory after build.
    Returns the path to the output EPUB file.
    """
    temp_dir = Path(temp_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load metadata
    meta_path = temp_dir / "metadata.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Metadata not found: {meta_path}. Run parse step first.")

    with open(meta_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    console.print(f"[bold]Building EPUB:[/] {metadata['title']}")

    book = epub.EpubBook()
    book.set_title(metadata.get("title", "Untitled"))
    book.set_language(metadata.get("language", "en"))
    if metadata.get("creator"):
        book.add_author(metadata["creator"])

    html_dir = temp_dir / "html"

    # Dictionary to map original item id -> new epub item
    item_map = {}

    # Collect all resource filenames for image path rewriting
    resource_filenames = {r["file_name"] for r in metadata.get("resources", [])}
    # Also include cover image so title-page references to it get rewritten
    if metadata.get("cover"):
        resource_filenames.add(metadata["cover"])

    # Add document items in spine order
    spine = []
    for doc in metadata.get("ordered_docs", []):
        filepath = html_dir / doc["file_name"]
        if not filepath.exists():
            console.print(f"  [yellow]Skipping missing file: {filepath.name}[/]")
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Strip XML declaration — ebooklib's HTML parser doesn't handle it
        content = _strip_xml_decl(content)

        # Rewrite image src paths to flat filenames (EPUB stores all resources flat)
        content = _fix_image_srcs(content, resource_filenames)
        # Also fix any CSS url() references in inline <style> blocks
        content = _fix_css_urls(content, resource_filenames)

        chapter = epub.EpubHtml(
            title=doc.get("file_name", ""),
            file_name=doc["file_name"],
            lang=metadata.get("language", "en"),
        )
        chapter.set_content(content)
        book.add_item(chapter)
        item_map[doc["id"]] = chapter
        spine.append(chapter)

    # Add resource items (images, CSS, fonts, etc.)
    for res in metadata.get("resources", []):
        filepath = temp_dir / res["href"]
        if not filepath.exists():
            continue

        file_name = res["file_name"]

        # Skip NCX — ebooklib auto-generates it from book.toc
        if file_name.endswith(".ncx"):
            continue
        res_type = res.get("type", "")
        ext = Path(file_name).suffix.lower()

        if res_type in ("1",) or ext in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp"):
            with open(filepath, "rb") as f:
                img_data = f.read()
            img_item = epub.EpubImage()
            img_item.file_name = file_name
            img_item.set_content(img_data)
            book.add_item(img_item)
            item_map[res["id"]] = img_item

        elif res_type in ("2",) or ext in (".css",):
            with open(filepath, "r", encoding="utf-8") as f:
                css_content = f.read()
            css_content = _fix_css_urls(css_content, resource_filenames)
            css_item = epub.EpubItem(
                uid=res["id"],
                file_name=file_name,
                media_type="text/css",
                content=css_content,
            )
            book.add_item(css_item)
            item_map[res["id"]] = css_item

        else:
            # Other resource: read as binary
            with open(filepath, "rb") as f:
                raw = f.read()
            ext_item = epub.EpubItem(
                uid=res["id"],
                file_name=file_name,
                media_type="application/octet-stream",
                content=raw,
            )
            book.add_item(ext_item)
            item_map[res["id"]] = ext_item

    # Set cover image (ebooklib auto-adds the cover file and cover.xhtml page)
    if metadata.get("cover"):
        cover_path = temp_dir / "resources" / metadata["cover"]
        if cover_path.exists():
            with open(cover_path, "rb") as f:
                cover_data = f.read()
            book.set_cover(metadata["cover"], cover_data)

    # Set spine (reading order)
    book.spine = spine

    # Build TOC from parsed metadata
    if metadata.get("toc"):
        book.toc = _build_toc_links(metadata["toc"], item_map)
    elif spine:
        book.toc = [(epub.Section(metadata.get("title", "Book")), spine)]
    else:
        book.toc = []

    book.add_item(epub.EpubNcx())

    # Navigation document
    book.add_item(epub.EpubNav())

    # Output filename
    safe_title = _safe_filename(metadata.get("title", "output"))
    output_path = output_dir / f"{safe_title}_bilingual.epub"

    epub.write_epub(str(output_path), book)
    console.print(f"[green]EPUB written:[/] {output_path}")

    # Clean up temp directory if requested
    if cleanup and temp_dir.exists():
        shutil.rmtree(temp_dir)
        console.print("[green]Temp directory cleaned.[/]")
    elif not cleanup:
        console.print("[dim]Temp directory kept for reuse. Run with --cleanup to remove.[/]")

    return str(output_path)


def _build_toc_links(toc_entries: list, item_map: dict) -> list:
    """Build TOC links from metadata TOC entries, mapping to epub items."""
    result = []
    for entry in toc_entries:
        link = _make_toc_entry(entry, item_map)
        if link:
            result.append(link)
    return result


def _make_toc_entry(entry: dict, item_map: dict):
    """Create a single TOC entry. Returns Link, or (Section, [children]) tuple, or None.

    Normalizes href to just the filename — ebooklib stores files flat in EPUB/,
    so path prefixes like "xhtml/" or "EPUB/..." must be stripped.
    """
    href = entry.get("href", "")
    title = entry.get("title", "")

    # Normalize href: strip directory prefix from file path, keep fragment
    fragment = ""
    if href and "#" in href:
        href, fragment = href.split("#", 1)
    if href and "/" in href:
        href = href.rsplit("/", 1)[-1]
    if fragment:
        href = f"{href}#{fragment}"

    if "children" in entry and entry["children"]:
        child_entries = []
        for child in entry["children"]:
            child_result = _make_toc_entry(child, item_map)
            if child_result:
                child_entries.append(child_result)

        if not child_entries:
            if href:
                return epub.Link(href, title, title)
            return None

        section = epub.Section(title)
        if href:
            section.href = href
        return (section, child_entries)
    else:
        if not href:
            return None
        return epub.Link(href, title, title)


def _safe_filename(name: str) -> str:
    """Remove unsafe characters from filename."""
    unsafe = '<>:"/\\|?*'
    for c in unsafe:
        name = name.replace(c, "_")
    return name.strip()[:100]


def _strip_xml_decl(content: str) -> str:
    """Remove <?xml ...?> declaration and DOCTYPE that break lxml's HTML parser."""
    content = re.sub(r'<\?xml[^?]*\?>', '', content, count=1)
    content = re.sub(r'<!DOCTYPE[^>]*>', '', content, count=1)
    return content


def _fix_image_srcs(content: str, resource_filenames: set) -> str:
    """Rewrite image src attributes to flat filenames. EPUB stores all resources flat,
    so paths like 'images/fig1.png' must become just 'fig1.png'."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(content, "lxml")
    changed = False

    for tag in soup.find_all(["img", "image"]):
        src = str(tag.get("src") or tag.get("href", ""))
        if not src:
            continue

        # Strip fragment/query from src for matching
        clean_src = src.split("#")[0].split("?")[0]
        filename = clean_src.rsplit("/", 1)[-1]

        if filename in resource_filenames and filename != src:
            tag["src"] = filename
            changed = True

    return str(soup) if changed else content


def _fix_css_urls(content: str, resource_filenames: set) -> str:
    """Rewrite url() paths in CSS to flat filenames. EPUB stores all resources flat,
    so url(resources/icon.png) must become url(icon.png)."""
    import re

    def replace_url(match):
        inner = match.group(1).strip()
        # Strip quotes
        path = inner.strip('"').strip("'").strip()
        # Strip fragment/query for matching
        clean_path = path.split("#")[0].split("?")[0]
        filename = clean_path.rsplit("/", 1)[-1]
        if filename in resource_filenames and filename != path:
            quote = '"' if '"' in inner else ("'" if "'" in inner else "")
            return f"url({quote}{filename}{quote})"
        return match.group(0)

    return re.sub(r'url\(([^)]+)\)', replace_url, content)
