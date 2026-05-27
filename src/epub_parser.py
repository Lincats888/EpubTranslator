import json
import shutil
from pathlib import Path
from ebooklib import epub, ITEM_COVER, ITEM_DOCUMENT, ITEM_IMAGE, ITEM_STYLE, ITEM_NAVIGATION
from rich.console import Console
from rich.progress import Progress

console = Console()


def parse_epub(epub_path: str | Path, temp_dir: str | Path = "temp") -> dict:
    """Parse an EPUB file, extract HTML and resources to temp directory.

    Returns metadata dict with spine order, manifest info, etc.
    """
    epub_path = Path(epub_path)
    temp_dir = Path(temp_dir)
    html_dir = temp_dir / "html"
    res_dir = temp_dir / "resources"

    # Clean and recreate temp dirs
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    html_dir.mkdir(parents=True, exist_ok=True)
    res_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"[bold]Parsing EPUB:[/] {epub_path.name}")
    book = epub.read_epub(str(epub_path))

    metadata = {
        "title": _get_title(book),
        "creator": _get_creator(book),
        "language": _get_language(book),
        "spine": [],
        "documents": [],
        "resources": [],
        "toc": [],
        "cover": None,
    }

    # Build lookup: item id -> item
    item_map = {}
    for item in book.get_items():
        item_map[item.id] = item

    # Collect spine document IDs (reading order)
    spine_ids = []
    for item_id, _linear in book.spine:
        spine_ids.append(item_id)

    # Find cover image first (before processing items, to deduplicate)
    cover_file = None
    for item in book.get_items():
        if item.get_type() == ITEM_COVER:
            cover_file = item.get_name() or f"{item.id}.png"
            break

    # Process items with progress
    items = list(book.get_items())
    with Progress() as progress:
        task = progress.add_task("[cyan]Extracting files...", total=len(items))

        for item in items:
            item_type = item.get_type()
            file_name = item.get_name() or f"{item.id}.xhtml"

            if item_type == ITEM_DOCUMENT:
                dest = html_dir / Path(file_name).name
                _write_item_content(item, dest)
                metadata["documents"].append({
                    "id": item.id,
                    "file_name": Path(file_name).name,
                    "href": str(dest.relative_to(temp_dir)),
                })

            elif item_type == ITEM_COVER:
                dest = res_dir / Path(file_name).name
                _write_item_content(item, dest)
                metadata["cover"] = Path(file_name).name

            elif item_type in (ITEM_IMAGE, ITEM_STYLE, ITEM_NAVIGATION):
                if cover_file and Path(file_name).name == cover_file:
                    progress.advance(task)
                    continue
                dest = res_dir / Path(file_name).name
                _write_item_content(item, dest)
                metadata["resources"].append({
                    "id": item.id,
                    "file_name": Path(file_name).name,
                    "type": str(item_type),
                    "href": str(dest.relative_to(temp_dir)),
                })

            else:
                # Fonts, scripts, etc. — keep as resources
                dest = res_dir / Path(file_name).name
                _write_item_content(item, dest)
                metadata["resources"].append({
                    "id": item.id,
                    "file_name": Path(file_name).name,
                    "type": str(item_type),
                    "href": str(dest.relative_to(temp_dir)),
                })

            progress.advance(task)

    # Build spine order (references to documents dict)
    for spine_id in spine_ids:
        if spine_id in item_map:
            item = item_map[spine_id]
            metadata["spine"].append(item.id)

    # Build documents list in spine order with filenames
    metadata["ordered_docs"] = []
    for spine_id in metadata["spine"]:
        for doc in metadata["documents"]:
            if doc["id"] == spine_id:
                metadata["ordered_docs"].append(doc)
                break

    # Extract TOC structure
    metadata["toc"] = _extract_toc(book)

    # Save metadata
    meta_path = temp_dir / "metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    console.print(f"[green]Parsed:[/] {len(metadata['documents'])} documents, "
                  f"{len(metadata['resources'])} resources")
    console.print(f"[green]Spine order:[/] {len(metadata['spine'])} items")
    console.print(f"[green]TOC entries:[/] {len(metadata['toc'])}")

    return metadata


def _write_item_content(item, dest: Path):
    content = item.get_content()
    if isinstance(content, str):
        with open(dest, "w", encoding="utf-8") as f:
            f.write(content)
    else:
        with open(dest, "wb") as f:
            f.write(content)


def _get_title(book) -> str:
    titles = book.get_metadata("DC", "title")
    if titles:
        return titles[0][0]
    return "Untitled"


def _get_creator(book) -> str:
    creators = book.get_metadata("DC", "creator")
    if creators:
        return creators[0][0]
    return ""


def _get_language(book) -> str:
    langs = book.get_metadata("DC", "language")
    if langs:
        return langs[0][0]
    return "en"


def _extract_toc(book) -> list:
    """Extract table of contents as a list of {title, href} dicts."""
    toc_entries = []
    try:
        for entry in book.toc:
            if isinstance(entry, tuple):
                flattened = _flatten_toc(entry)
                if flattened:
                    toc_entries.append(flattened)
            elif isinstance(entry, epub.Link):
                if entry.href:
                    toc_entries.append({
                        "title": entry.title,
                        "href": entry.href,
                    })
            elif isinstance(entry, epub.Section):
                toc_entries.append({
                    "title": entry.title,
                    "href": entry.href or "",
                    "children": [_flatten_toc(c) for c in entry.subsections] if entry.subsections else [],
                })
    except Exception:
        pass
    return toc_entries


def _flatten_toc(item) -> dict | None:
    """Recursively flatten a TOC entry. Returns None if no href."""
    if isinstance(item, epub.Link):
        if item.href:
            return {"title": item.title, "href": item.href}
        return None
    elif isinstance(item, tuple):
        parent, children = item[0], item[1] if len(item) > 1 else []
        if isinstance(parent, (epub.Link, epub.Section)):
            result = {
                "title": parent.title,
                "href": parent.href or "",
                "children": [c for c in (_flatten_toc(c) for c in children) if c],
            }
            # Only return if has href or children
            if result["href"] or result["children"]:
                return result
        return None
    return None
