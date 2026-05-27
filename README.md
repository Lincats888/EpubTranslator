# EPUB 双语翻译器

将英文 EPUB 翻译为中英双语（或纯中文）EPUB 的 CLI 工具。逐段翻译 HTML，保留原始格式、图片、目录结构和代码块。

## 功能特性

- **中英双语输出** — 每段原文后紧跟中文译文，用灰白底样式区分
- **纯中文模式** — 可切换为仅保留中文译文
- **代码保护** — 自动跳过 `<pre>`、`<code>` 块，可配置自定义选择器
- **保留原格式** — 标题、列表、引用等标签类型完整保留
- **目录翻译** — TOC 标题同步翻译为双语或纯中文
- **断点续传** — 翻译中断后重跑跳过已完成文件
- **批量翻译** — 每 10 段一组调用 API，高效省 token

## 安装

```bash
git clone https://github.com/Lincats888/EpubTranslator.git
cd EpubTranslator
pip install -r requirements.txt
```

### 依赖

| 库 | 用途 |
|---|---|
| `typer` | CLI 框架 |
| `rich` | 进度条和彩色输出 |
| `beautifulsoup4` + `lxml` | HTML 解析与修改 |
| `openai` | DeepSeek API 调用（兼容接口） |
| `ebooklib` | EPUB 读写 |

## 快速开始

```bash
# 1. 复制配置模板，填入你的 DeepSeek API Key
cp config.example.json config.json

# 2. 一键翻译
python main.py translate book.epub

# 3. 输出在 output/ 目录下
```

## 配置

`config.json` 示例：

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

| 配置项 | 说明 |
|---|---|
| `api_key` | DeepSeek API Key（必填，[获取地址](https://platform.deepseek.com)） |
| `model` | 模型名称，默认 `deepseek-chat` |
| `temperature` | 翻译温度，默认 0.3 |
| `max_tokens` | 每次请求最大 token 数 |
| `code_selectors` | 跳过翻译的 CSS 选择器，如 `["pre", "code", "pre.programlisting"]` |
| `output_mode` | `"bilingual"`（中英双语）或 `"chinese_only"`（纯中文） |

## 命令

```bash
# 一键全流程：解析 → 翻译 → 构建
python main.py translate book.epub

# 分步执行（适合调试）
python main.py parse book.epub           # 步骤1: 解析 EPUB 到 temp/
python main.py run                        # 步骤2: 翻译 temp/html/ 中的文件
python main.py build                      # 步骤3: 构建 EPUB，输出到 output/
python main.py build --cleanup            # 步骤3: 构建并清理 temp/

# 自定义目录
python main.py translate book.epub -o myoutput/ -t mytemp/
python main.py translate book.epub -c myconfig.json
```

## 项目结构

```
EpubTranslator/
├── main.py                  # CLI 入口（parse / run / build / translate）
├── config.example.json      # 配置模板（真实 config.json 不入 git）
├── requirements.txt         # Python 依赖
├── README.md
├── src/
│   ├── config.py            # 配置加载与验证
│   ├── epub_parser.py       # EPUB 解析 → HTML + 资源 + metadata.json
│   ├── translator.py        # HTML 逐段翻译（DeepSeek API）
│   └── epub_builder.py      # 重建 EPUB + 路径重写
├── create_test_epub.py      # 测试 EPUB 生成器（普通结构）
├── create_nested_test.py    # 测试 EPUB 生成器（嵌套目录）
└── test_comprehensive.py    # 端到端集成测试
```

## 数据流

```
book.epub ──parse──> temp/html/*.xhtml + temp/resources/* + temp/metadata.json
temp/html/* ──run──> temp/html/*.xhtml（原文 + 译文）
temp/* ──build──> output/<书名>_bilingual.epub
```

## 测试

```bash
# 生成测试 EPUB 并运行集成测试（需要 API key）
python create_test_epub.py
python test_comprehensive.py

# 创建带嵌套目录结构的测试 EPUB
python create_nested_test.py
```

## License

MIT
