"""Create a test EPUB with a cover image."""
from pathlib import Path
from ebooklib import epub

# Create a simple cover image (1x1 pixel green PNG)
import struct
import zlib

def create_png(width, height, color=(0, 128, 0)):
    """Create a minimal PNG file bytes."""
    def chunk(chunk_type, data):
        chunk_data = chunk_type + data
        return struct.pack('>I', len(data)) + chunk_data + struct.pack('>I', zlib.crc32(chunk_data) & 0xffffffff)

    header = b'\x89PNG\r\n\x1a\n'
    ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
    raw = b''
    for y in range(height):
        raw += b'\x00'  # filter none
        for x in range(width):
            raw += bytes(color)
    idat = chunk(b'IDAT', zlib.compress(raw))
    iend = chunk(b'IEND', b'')
    return header + ihdr + idat + iend

cover_bytes = create_png(100, 150, (50, 100, 50))  # dark green

book = epub.EpubBook()
book.set_title("Book With Cover")
book.set_language("en")
book.add_author("Test Author")

# Cover image
cover_img = epub.EpubImage()
cover_img.file_name = "cover.png"
cover_img.set_content(cover_bytes)
cover_img.id = "cover_img"
book.add_item(cover_img)

# Chapter
c1 = epub.EpubHtml(title="Chapter 1", file_name="chap01.xhtml", lang="en")
c1.set_content("<html><body><h1>Chapter 1</h1><p>Hello world.</p></body></html>")
book.add_item(c1)

book.spine = [c1]
book.toc = [epub.Link("chap01.xhtml", "Chapter 1", "ch1")]

# Set cover image
book.set_cover("cover.png", cover_bytes)

book.add_item(epub.EpubNcx())
book.add_item(epub.EpubNav())

output = Path(__file__).parent / "cover_test.epub"
epub.write_epub(str(output), book)
print(f"Created: {output}")
