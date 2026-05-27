"""Comprehensive test: bilingual TOC, image paths, code blocks, element tags.

Simulates a real EPUB with subdirectory paths, nested TOC, images, code blocks.
"""
import json
import re
import sys
import struct
import zlib
import shutil
from pathlib import Path

from ebooklib import epub, ITEM_DOCUMENT
from bs4 import BeautifulSoup

# ── Helpers ──────────────────────────────────────────────────────────────

def tiny_png(color=(50, 100, 50)):
    def chunk(t, d):
        c = t + d
        return struct.pack('>I',len(d)) + c + struct.pack('>I',zlib.crc32(c)&0xffffffff)
    raw = b'\x00' + bytes(color)
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB',1,1,8,2,0,0,0))
            + chunk(b'IDAT', zlib.compress(raw))
            + chunk(b'IEND', b''))

def print_toc(entries, indent=0):
    for e in entries:
        if isinstance(e, tuple):
            section, children = e
            print('  ' * indent + f'[Section] {section.title}')
            print_toc(children, indent + 1)
        else:
            print('  ' * indent + f'[Link] {e.title} -> {e.href}')

def find_broken_links(book):
    item_names = {item.get_name() for item in book.get_items()
                  if item.get_type() == ITEM_DOCUMENT}
    # Also add nav and ncx
    item_names |= {item.get_name() for item in book.get_items()}
    broken = []
    def check(entries):
        for e in entries:
            if isinstance(e, tuple):
                check(e[1])
            elif hasattr(e, 'href') and e.href:
                if e.href not in item_names:
                    broken.append((e.title, e.href))
    check(book.toc)
    return broken

def make_chapter(num, title, body, img_ref=None):
    c = epub.EpubHtml(title=title, file_name=f"xhtml/ch{num:02d}.xhtml", lang="en")
    img_line = f'<img src="../images/{img_ref}" alt="{img_ref}"/>' if img_ref else ""
    content = f"""<html>
<head><link rel="stylesheet" type="text/css" href="../styles/main.css"/></head>
<body>
<h1>{title}</h1>
{img_line}
{body}
</body>
</html>"""
    c.set_content(content)
    return c

failed = False

# ── Step 1: Create test EPUB ─────────────────────────────────────────────
print("=" * 60)
print("STEP 1: Creating test EPUB with realistic structure")
print("=" * 60)

book = epub.EpubBook()
book.set_title("Comprehensive Test Book")
book.set_language("en")
book.add_author("Test Author")

# Images in subdirectory
img1 = epub.EpubImage(); img1.file_name = "images/cover.png"
img1.set_content(tiny_png((100,50,50))); img1.id = "img_cover"
book.add_item(img1)

img2 = epub.EpubImage(); img2.file_name = "images/fig1.png"
img2.set_content(tiny_png((50,100,50))); img2.id = "img_fig1"
book.add_item(img2)

# CSS icon for background-image test
img3 = epub.EpubImage(); img3.file_name = "images/icon-warning.png"
img3.set_content(tiny_png((200,200,50))); img3.id = "img_icon"
book.add_item(img3)

# CSS in subdirectory with url() references
css_content = b"""body { font-family: serif; }
aside.warning {
    background-image: url("../images/icon-warning.png");
    padding-left: 30px;
}"""
css = epub.EpubItem(uid="css_main", file_name="styles/main.css",
                    media_type="text/css",
                    content=css_content)
book.add_item(css)

# Chapters
chapters_data = [
    ("Introduction", "<p>Welcome to this comprehensive guide about programming.</p><p>This book covers many important topics.</p>", None),
    ("Getting Started", '<p>First, install Python. Here is a simple example:</p><pre><code>print("Hello, World!")</code></pre><p>This prints a greeting.</p>', None),
    ("Advanced Topics", '<p>Let us look at recursion:</p><pre><code>def fib(n):\n    if n &lt;= 1:\n        return n\n    return fib(n-1) + fib(n-2)</code></pre><p>Recursion is powerful but can be slow.</p>', "fig1.png"),
    ("Best Practices", "<p>Write clean code. Use meaningful names.</p><blockquote>Code is read more often than it is written.</blockquote><p>Keep functions small and focused.</p>", None),
    ("Conclusion", "<p>We have covered the essentials. Practice regularly.</p><p>Thank you for reading this book.</p>", None),
]

spine_items = []
for i, (title, body, img) in enumerate(chapters_data, 1):
    c = make_chapter(i, title, body, img)
    book.add_item(c)
    spine_items.append(c)

# 2-level TOC with subdirectory hrefs (like real EPUBs)
book.toc = [
    (epub.Section("Part I: Fundamentals"), [
        epub.Link("xhtml/ch01.xhtml", "Introduction", "ch01"),
        epub.Link("xhtml/ch02.xhtml", "Getting Started", "ch02"),
    ]),
    (epub.Section("Part II: Deep Dive"), [
        epub.Link("xhtml/ch03.xhtml", "Advanced Topics", "ch03"),
        epub.Link("xhtml/ch04.xhtml", "Best Practices", "ch04"),
    ]),
    epub.Link("xhtml/ch05.xhtml", "Conclusion", "ch05"),
]

book.spine = spine_items
book.add_item(epub.EpubNcx())
book.add_item(epub.EpubNav())

test_path = Path(__file__).parent / "comprehensive_test.epub"
epub.write_epub(str(test_path), book)
print(f"Created: {test_path}")

# ── Step 2: Parse ────────────────────────────────────────────────────────
print()
print("=" * 60)
print("STEP 2: Parse")
print("=" * 60)

from src.epub_parser import parse_epub
tmp = Path("temp_test")
if tmp.exists():
    shutil.rmtree(tmp)

metadata = parse_epub(str(test_path), tmp)
print(f"Resources: {[r['file_name'] for r in metadata['resources']]}")
print(f"Ordered docs: {[d['file_name'] for d in metadata['ordered_docs']]}")

# Verify image extraction
img_names = {r["file_name"] for r in metadata["resources"]}
assert "cover.png" in img_names, "FAIL: cover.png not in resources!"
assert "fig1.png" in img_names, "FAIL: fig1.png not in resources!"
print("PASS: All images extracted to flat filenames")

# Verify html has image src with path
ch03 = tmp / "html" / "ch03.xhtml"
with open(ch03) as f:
    ch03_content = f.read()
assert "../images/fig1.png" in ch03_content, "FAIL: image src not found in ch03"
print("PASS: ch03 has original image path '../images/fig1.png'")

# ── Step 3: Translate ────────────────────────────────────────────────────
print()
print("=" * 60)
print("STEP 3: Translate")
print("=" * 60)

from src.config import load_config
from src.translator import translate_html_dir

config = load_config("config.json")
translate_html_dir(
    tmp / "html", config,
    progress_file=tmp / "progress.json",
    metadata_file=tmp / "metadata.json",
)

# Check TOC was translated (bilingual format: "English / Chinese")
with open(tmp / "metadata.json", encoding="utf-8") as f:
    meta = json.load(f)
print()
print("Translated TOC:")
for entry in meta["toc"]:
    if "children" in entry:
        print(f"  [Section] {entry['title']}")
        for child in entry["children"]:
            print(f"    [Link] {child['title']}")
    else:
        print(f"  [Link] {entry['title']}")

# Verify bilingual format
for entry in meta["toc"]:
    if "children" in entry:
        assert " / " in entry["title"], f"FAIL: Section title not bilingual: {entry['title']}"
        for child in entry["children"]:
            assert " / " in child["title"], f"FAIL: Link title not bilingual: {child['title']}"
    else:
        assert " / " in entry["title"], f"FAIL: Link title not bilingual: {entry['title']}"
print("PASS: All TOC titles are bilingual (English / Chinese)")

# ── Step 4: Build ────────────────────────────────────────────────────────
print()
print("=" * 60)
print("STEP 4: Build EPUB")
print("=" * 60)

from src.epub_builder import build_epub
out_dir = Path("output_test")
result_path = build_epub(tmp, out_dir, cleanup=False)
print(f"Built: {result_path}")

# ── Step 5: Verify output EPUB ───────────────────────────────────────────
print()
print("=" * 60)
print("STEP 5: Verify output EPUB")
print("=" * 60)

built = epub.read_epub(str(result_path))
print(f"Title: {built.title}")

# List all items
item_map = {}
doc_items = set()
for item in built.get_items():
    name = item.get_name()
    print(f"  [{item.get_type()}] {name}")
    item_map[name] = item
    if item.get_type() == ITEM_DOCUMENT:
        doc_items.add(name)

# Check required files
required = ["ch01.xhtml", "ch02.xhtml", "ch03.xhtml", "ch04.xhtml",
            "ch05.xhtml", "cover.png", "fig1.png", "icon-warning.png",
	            "main.css"]
for name in required:
    assert name in item_map, f"FAIL: {name} missing from EPUB"
print("PASS: All required files present")

# ── TEST A: TOC links ───────────────────────────────────────────────────
print()
print("--- Test A: TOC links ---")
print_toc(built.toc)

broken = find_broken_links(built)
if broken:
    print(f"FAIL: {len(broken)} broken TOC links:")
    for title, href in broken:
        print(f"  '{title}' -> {href}")
    failed = True
else:
    print("PASS: All TOC links point to existing files")

# ── TEST B: Image src paths ─────────────────────────────────────────────
print()
print("--- Test B: Image paths ---")
for item in built.get_items():
    if item.get_name() == "ch03.xhtml":
        content = item.get_content().decode() if isinstance(item.get_content(), bytes) else item.get_content()
        soup = BeautifulSoup(content, "lxml")
        for img in soup.find_all("img"):
            src = img.get("src", "")
            if src in item_map:
                print(f"  PASS: img src='{src}' -> found in EPUB")
            else:
                print(f"  FAIL: img src='{src}' -> NOT FOUND in EPUB")
                failed = True

        # Verify path was rewritten (no ../ prefix)
        for img in soup.find_all("img"):
            src = img.get("src", "")
            if "../" in src:
                print(f"  FAIL: img src still has relative path: {src}")
                failed = True

# ── TEST B2: CSS url() paths ───────────────────────────────────────────
print()
print("--- Test B2: CSS url() paths ---")
for item in built.get_items():
    if item.get_name() == "main.css":
        content = item.get_content()
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        print(f"  CSS content:\n{content}")
        if "url(\"icon-warning.png\")" in content:
            print("  PASS: CSS url() path rewritten to flat filename")
        elif "url(\"../images/icon-warning.png\")" in content:
            print("  FAIL: CSS url() path NOT rewritten")
            failed = True
        elif "icon-warning.png" not in content:
            print("  FAIL: icon-warning.png reference missing from CSS")
            failed = True

# ── TEST C: Element tags preserved ──────────────────────────────────────
print()
print("--- Test C: Element tags ---")
for item in built.get_items():
    if item.get_name() == "ch01.xhtml":
        content = item.get_content().decode() if isinstance(item.get_content(), bytes) else item.get_content()
        soup = BeautifulSoup(content, "lxml")
        trans_tags = {t.name for t in soup.find_all(class_="trans-bilingual")}
        print(f"  Translation tags: {trans_tags}")
        # h1 should be in there (headings)
        if "h1" in trans_tags:
            print("  PASS: h1 tags preserved in translations")
        else:
            print("  FAIL: no h1 translation tags found")
            failed = True

# ── TEST D: Code blocks preserved ───────────────────────────────────────
print()
print("--- Test D: Code blocks ---")
for item in built.get_items():
    if item.get_name() == "ch02.xhtml":
        content = item.get_content().decode() if isinstance(item.get_content(), bytes) else item.get_content()
        soup = BeautifulSoup(content, "lxml")
        pres = soup.find_all("pre")
        codes = soup.find_all("code")
        if pres and codes:
            print(f"  PASS: {len(pres)} pre, {len(codes)} code blocks preserved")
            # Check code wasn't translated
            for code in codes:
                text = code.get_text()
                if "print" in text:
                    print(f"  PASS: code content intact: {text.strip()[:60]}")
        else:
            print(f"  FAIL: pre={len(pres)}, code={len(codes)}")
            failed = True

# ── Final verdict ────────────────────────────────────────────────────────
print()
print("=" * 60)
if failed:
    print("SOME TESTS FAILED")
    sys.exit(1)
else:
    print("ALL TESTS PASSED")
print("=" * 60)

# Cleanup
shutil.rmtree(tmp, ignore_errors=True)
shutil.rmtree(out_dir, ignore_errors=True)
