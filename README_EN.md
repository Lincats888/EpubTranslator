# 📚 EPUB Bilingual Translator

> Translate English EPUBs into English-Chinese bilingual (or Chinese-only) EPUBs. A pure CLI tool that translates paragraph-by-paragraph, preserving formatting, images, TOC structure, and code blocks.

[中文版](README.md)

## ✨ Features

- **Bilingual Output** — Each original paragraph followed by Chinese translation with subtle gray background
- **Chinese-Only Mode** — Optionally output only Chinese translations
- **Code Protection** — Auto-skips `<pre>`, `<code>` blocks; supports custom selectors
- **Format Preservation** — Headings, lists, blockquotes, and other tag types remain intact
- **TOC Translation** — Table of contents titles translated in sync
- **Resumable** — Interrupted translations resume where they left off
- **Batch API Calls** — 10 paragraphs per request for efficient token usage

## 🚀 Installation

```bash
git clone https://github.com/Lincats888/EpubTranslator.git
cd EpubTranslator
pip install -r requirements.txt
```

### Dependencies

| Library | Purpose |
|---|---|
| `typer` | CLI framework |
| `rich` | Progress bars & colored output |
| `beautifulsoup4` + `lxml` | HTML parsing & manipulation |
| `openai` | DeepSeek API via OpenAI-compatible SDK |
| `ebooklib` | EPUB read & write |

## 🏃 Quick Start

```bash
# 1. Copy config template and fill in your DeepSeek API Key
cp config.example.json config.json

# 2. One-command translation
python main.py translate book.epub

# 3. Find the output in output/ directory
```

## ⚙️ Configuration

`config.json` example:

```json
{
    "api_key": "sk-xxx",
    "model": "deepseek-chat",
    "temperature": 0.3,
    "max_tokens": 2000,
    "code_selectors": ["pre", "code"],
    "output_mode": "bilingual"
}
```

| Option | Description |
|---|---|
| `api_key` | DeepSeek API Key (required, [get one here](https://platform.deepseek.com)) |
| `model` | Model name, default: `deepseek-chat` |
| `temperature` | Translation temperature, default: 0.3 |
| `max_tokens` | Max tokens per request |
| `code_selectors` | CSS selectors to skip, e.g. `["pre", "code", "pre.programlisting"]` |
| `output_mode` | `"bilingual"` (English + Chinese) or `"chinese_only"` |

## 📋 Commands

```bash
# Full pipeline: parse → translate → build
python main.py translate book.epub

# Step-by-step (useful for debugging)
python main.py parse book.epub         # Step 1: Extract EPUB to temp/
python main.py run                     # Step 2: Translate HTML files in temp/
python main.py build                   # Step 3: Build EPUB, output to output/
python main.py build --cleanup         # Step 3: Build and clean up temp/

# Custom directories
python main.py translate book.epub -o myoutput/ -t mytemp/
python main.py translate book.epub -c myconfig.json
```

## 📁 Project Structure

```
EpubTranslator/
├── main.py                  # CLI entry point (parse / run / build / translate)
├── config.example.json      # Config template (real config.json is git-ignored)
├── requirements.txt         # Python dependencies
├── README.md                # 中文文档
├── README_EN.md             # English documentation
├── src/
│   ├── config.py            # Config loading & validation
│   ├── epub_parser.py       # EPUB → HTML + resources + metadata.json
│   ├── translator.py        # Paragraph-by-paragraph translation (DeepSeek API)
│   └── epub_builder.py      # EPUB rebuild with path rewriting
├── create_test_epub.py      # Test EPUB generator (flat structure)
├── create_nested_test.py    # Test EPUB generator (nested TOC)
└── test_comprehensive.py    # End-to-end integration test
```

## 🔄 Data Flow

```
book.epub ──parse──> temp/html/*.xhtml + temp/resources/* + temp/metadata.json
temp/html/* ──run──> temp/html/*.xhtml (original + translation)
temp/* ──build──> output/<title>_bilingual.epub
```

## 🧪 Testing

```bash
# Generate test EPUB and run integration tests (requires API key)
python create_test_epub.py
python test_comprehensive.py

# Create test EPUB with nested TOC structure
python create_nested_test.py
```

## 📄 License

MIT
