"""Create a test EPUB with 2-level nested TOC to verify the fix."""
from ebooklib import epub
from pathlib import Path

book = epub.EpubBook()
book.set_title("Nested TOC Test")
book.set_language("en")
book.add_author("Test Author")

# Create chapters
chapters = {}
for i, title in enumerate(["Intro", "Getting Started", "Functions", "Classes", "Advanced", "Summary"], 1):
    c = epub.EpubHtml(title=title, file_name=f"chap{i:02d}.xhtml", lang="en")
    c.set_content(f"<html><body><h1>{title}</h1><p>Content of {title}.</p></body></html>")
    book.add_item(c)
    chapters[title] = c

# 2-level TOC:
# Part 1: Basics
#   Chapter 1: Intro
#   Chapter 2: Getting Started
# Part 2: Core
#   Chapter 3: Functions
#   Chapter 4: Classes
# Part 3: Extra
#   Chapter 5: Advanced
#   Chapter 6: Summary

book.toc = [
    (epub.Section("Part 1: Basics"), [
        epub.Link("chap01.xhtml", "Intro", "intro"),
        epub.Link("chap02.xhtml", "Getting Started", "start"),
    ]),
    (epub.Section("Part 2: Core"), [
        epub.Link("chap03.xhtml", "Functions", "func"),
        epub.Link("chap04.xhtml", "Classes", "class"),
    ]),
    (epub.Section("Part 3: Extra"), [
        epub.Link("chap05.xhtml", "Advanced", "adv"),
        epub.Link("chap06.xhtml", "Summary", "sum"),
    ]),
]

book.spine = list(chapters.values())
book.add_item(epub.EpubNcx())
book.add_item(epub.EpubNav())

output = Path(__file__).parent / "nested_test.epub"
epub.write_epub(str(output), book)
print(f"Created: {output}")
