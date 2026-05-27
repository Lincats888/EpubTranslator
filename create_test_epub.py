"""Create a test EPUB for verifying the translator pipeline."""
from ebooklib import epub
from pathlib import Path

book = epub.EpubBook()
book.set_title("Test Book - Python Programming Guide")
book.set_language("en")
book.add_author("Test Author")

# Chapter 1: Plain text
c1 = epub.EpubHtml(title="Introduction", file_name="chap01.xhtml", lang="en")
c1.set_content("""
<html>
<head><title>Introduction</title></head>
<body>
<h1>Introduction</h1>
<p>Welcome to this programming guide. This book covers essential topics in software development.</p>
<p>Before we begin, let us review some fundamental concepts that will help you understand the material.</p>
<p>Programming is both an art and a science. It requires creativity and logical thinking.</p>
<h2>Getting Started</h2>
<p>To start programming, you need a good text editor and a desire to learn. The journey may be challenging but rewarding.</p>
</body>
</html>
""")

# Chapter 2: With code blocks
c2 = epub.EpubHtml(title="Code Examples", file_name="chap02.xhtml", lang="en")
c2.set_content("""
<html>
<head><title>Code Examples</title></head>
<body>
<h1>Code Examples</h1>
<p>Here is a simple Python function that calculates the factorial of a number:</p>
<pre><code>
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

# Example usage
print(factorial(5))  # Output: 120
</code></pre>
<p>The function uses recursion, a powerful technique where a function calls itself.</p>
<p>Now let us look at an iterative version:</p>
<pre><code>
def factorial_iterative(n):
    result = 1
    for i in range(1, n + 1):
        result *= i
    return result
</code></pre>
<p>Both approaches achieve the same result, but they differ in performance and readability.</p>
<h2>Best Practices</h2>
<p>Always write clean, readable code. Use meaningful variable names and add comments where necessary.</p>
</body>
</html>
""")

# Chapter 3: Foreword-like content
c3 = epub.EpubHtml(title="Preface", file_name="chap03.xhtml", lang="en")
c3.set_content("""
<html>
<head><title>Preface</title></head>
<body>
<h1>Preface</h1>
<p>This book was written for developers who want to deepen their understanding of programming.</p>
<blockquote>
Knowledge is of no value unless you put it into practice.
</blockquote>
<p>We hope you find this guide useful in your learning journey.</p>
</body>
</html>
""")

# Add chapters
book.add_item(c1)
book.add_item(c2)
book.add_item(c3)

# Set spine
book.spine = [c1, c2, c3]

# Set TOC
book.toc = [
    epub.Link("chap01.xhtml", "Introduction", "intro"),
    epub.Link("chap02.xhtml", "Code Examples", "code"),
    epub.Link("chap03.xhtml", "Preface", "preface"),
]

# Add navigation
book.add_item(epub.EpubNcx())
book.add_item(epub.EpubNav())

# Write
output = Path(__file__).parent / "test_book.epub"
epub.write_epub(str(output), book)
print(f"Test EPUB created: {output}")
