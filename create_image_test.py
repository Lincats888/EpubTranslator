"""Create a test EPUB with images for verifying image path fix."""
from ebooklib import epub
from pathlib import Path

# Create a simple 1x1 green PNG
import struct, zlib
def tiny_png():
    def chunk(t, d):
        c = t + d
        return struct.pack('>I',len(d)) + c + struct.pack('>I',zlib.crc32(c)&0xffffffff)
    raw = b'\x00' + bytes([0,128,0])
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB',1,1,8,2,0,0,0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')

png_bytes = tiny_png()

book = epub.EpubBook()
book.set_title("Image Test")
book.set_language("en")
book.add_author("Test")

# Image item with subdirectory path (simulating real EPUB structure)
img = epub.EpubImage()
img.file_name = "images/fig1.png"  # Path with subdirectory
img.set_content(png_bytes)
img.id = "img1"
book.add_item(img)

# Chapter with img tag referencing the subdirectory path
c1 = epub.EpubHtml(title="Chapter 1", file_name="xhtml/ch01.xhtml", lang="en")
c1.set_content("""
<html>
<body>
<h1>Chapter 1</h1>
<p>Below is an image:</p>
<img src="../images/fig1.png" alt="Test image"/>
<p>End of chapter.</p>
</body>
</html>
""")
book.add_item(c1)

book.spine = [c1]
book.toc = [epub.Link("xhtml/ch01.xhtml", "Chapter 1", "ch1")]
book.add_item(epub.EpubNcx())
book.add_item(epub.EpubNav())

output = Path(__file__).parent / "image_test.epub"
epub.write_epub(str(output), book)
print(f"Created: {output}")
