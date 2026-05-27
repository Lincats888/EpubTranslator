# EPUB 双语翻译器 (EPUB Bilingual Translator)

将英文 EPUB 翻译为中英双语 EPUB 的 CLI 工具。解析 EPUB → 逐段翻译 HTML → 合并输出双语 EPUB。

## 命令

```bash
python main.py translate book.epub              # 一键全流程
python main.py parse book.epub                  # 仅解压 EPUB 到 temp/
python main.py run                                # 仅翻译 temp/html/ 中的文件
python main.py build                              # 仅合并 + 清理，输出到 output/
```

选项：`-c/--config` 指定配置文件，`-t/--temp` 指定临时目录，`-o/--output` 指定输出目录。

## 文件结构

```
epubTranslater/
├── main.py              # Typer CLI 入口 (4 个命令: parse, run, build, translate)
├── config.json          # DeepSeek API Key + 翻译参数 (不入 git)
├── requirements.txt     # typer, rich, beautifulsoup4, lxml, openai, ebooklib
├── src/
│   ├── config.py        # load_config() — 读取/验证 config.json，填默认值
│   ├── epub_parser.py   # parse_epub() — 解压 EPUB，提取 HTML/资源到 temp/
│   ├── translator.py    # translate_html_dir() — 逐段翻译 HTML (DeepSeek API)
│   └── epub_builder.py  # build_epub() — 从 temp/ 重建 EPUB，清理 temp/
├── create_test_epub.py      # 测试用 EPUB 生成器 (普通)
├── create_nested_test.py    # 测试用 EPUB 生成器 (2层嵌套目录)
└── temp/                    # 临时工作目录 (不入 git)
```

## 数据流

```
book.epub ──parse──> temp/html/*.xhtml + temp/resources/* + temp/metadata.json
temp/html/* ──run──> temp/html/*.xhtml (原文+译文双语)
temp/* ──build──> output/<书名>_bilingual.epub ──> 清理 temp/
```

## 核心模块详解

### epub_parser.py
- 用 `ebooklib.epub.read_epub()` 读取 EPUB
- 遍历 spine 确定阅读顺序，提取所有 items
- HTML 文档 → `temp/html/`，图片/CSS 等 → `temp/resources/`
- 生成 `temp/metadata.json`：包含 title, creator, language, spine, ordered_docs, toc, resources, cover
- ordered_docs 是 spine 顺序的文档列表，供 translator 和 builder 使用
- nav.xhtml 作为文档提取但不进入 spine/ordered_docs，不会被翻译
- **封面处理**：先扫描 `ITEM_COVER` 类型获取封面文件名，后续处理时跳过同名的 `ITEM_IMAGE`，封面文件单独保存通过 `metadata["cover"]` 记录

### translator.py
- 只翻译 ordered_docs 中的文件（不翻译 nav.xhtml）
- 用 BeautifulSoup(lxml) 解析 HTML，筛选块级文本元素：`p, h1-h6, li, blockquote, figcaption, dt, dd, td, th, caption, summary, legend`
- **代码保护**：_is_inside_code() 检查元素是否在 `<pre>`, `<code>` 或配置的 `code_selectors` 内
- **批量翻译**：每 10 段一组发送给 DeepSeek，用 `---TRANSLATION_SEPARATOR---` 分隔回复
- **保留标签格式**：译文元素保留原标签名（h1 的译文也是 h1，li 的也是 li），加 `trans-bilingual` class
- 注入 dark green italic 样式到 `<head>`
- **断点续传**：`temp/progress.json` 记录已完成的文件名，中断重跑跳过已完成文件
- **目录翻译**：翻译完 HTML 后，自动翻译 `metadata.json` 中的 TOC 标题并回写
- DeepSeek API: OpenAI 兼容接口 `https://api.deepseek.com/v1`，用 `openai` SDK 调用
- 跳过 XML 解析警告 (XMLParsedAsHTMLWarning)

### epub_builder.py
- 读取 `temp/metadata.json`，用 ebooklib 构建新 EPUB
- **关键**：HTML 内容中的 `<?xml...?>` 和 `<!DOCTYPE>` 必须用 `_strip_xml_decl()` 去除，否则 ebooklib 的 lxml HTML parser 会报错
- 图片按二进制读入，用 EpubImage；CSS 用 EpubItem(text/css)
- **封面**：通过 `book.set_cover()` 设置，ebooklib 自动生成 cover.xhtml 和 `<meta name="cover">`，无需手动添加封面图片到 resources
- **跳过 NCX 文件**（.ncx）：ebooklib 通过 `EpubNcx()` 根据 book.toc 自动生成，重复添加会导致 Duplicate name 警告
- **TOC 重建**：ebooklib 内部用 tuple `(Section, [children])` 表示嵌套目录，不是 Section.subsections 属性。`_make_toc_entry` 对有 children 的节点返回 tuple
- build 完成后 `shutil.rmtree(temp/)` 清理临时目录

## 已知坑点

1. **ebooklib TOC 结构**：嵌套目录用 `(Section/Link, [children])` tuple，不能用 `section.subsections.append()`
2. **TOC 空 href**：Section 类型节点 href 可能为空（仅作分组），builder 需容忍空 href 的 Section
3. **XML 声明**：`<?xml version='1.0' encoding='utf-8'?>` 会导致 lxml HTML parser 报 `ValueError: Unicode strings with encoding declaration are not supported`，必须 strip
4. **NCX 重复**：ebooklib 的 `EpubNcx()` 自动生成 toc.ncx，不要从原 EPUB 添加
5. **nav.xhtml 解析**：如果包含在文档列表中但不在 spine 中，不应被翻译
6. **封面图片**：用 `book.set_cover()` 自动添加（生成 cover.xhtml + 设置 meta 元数据），不要手动将封面图片作为普通资源添加，否则会导致 Duplicate name

## config.json 格式

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

- `code_selectors` 支持扩展，如 `["pre", "code", "div.code", "pre.programlisting"]`
- `output_mode`: `"bilingual"` (默认，中英双语) 或 `"chinese_only"` (仅中文)。切换模式后会自动重新翻译，不会复用旧进度。

## 测试

```bash
python create_test_epub.py              # 生成普通测试 EPUB
python create_nested_test.py            # 生成 2 层嵌套目录测试 EPUB
python main.py translate test_book.epub  # 全流程测试 (需 API key)
```
