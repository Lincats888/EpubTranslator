"""EPUB Bilingual Translator — translate English EPUBs to English-Chinese bilingual EPUBs.

Usage:
    python main.py book.epub                      # Full pipeline
    python main.py book.epub -o output/           # Custom output dir
    python main.py book.epub --config myconf.json # Custom config
    python main.py parse book.epub                # Parse only
    python main.py run                          # Translate only (from temp/)
    python main.py build                          # Build + cleanup only
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from src.config import load_config
from src.epub_parser import parse_epub
from src.translator import translate_html_dir
from src.epub_builder import build_epub

app = typer.Typer(help="EPUB Bilingual Translator")
console = Console()


@app.command(name="parse")
def parse_cmd(
    epub_path: str = typer.Argument(..., help="Path to the English EPUB file"),
    temp_dir: str = typer.Option("temp", "--temp", "-t", help="Temporary working directory"),
):
    """Step 1: Parse EPUB into HTML and resources."""
    if not Path(epub_path).exists():
        console.print(f"[red]File not found: {epub_path}[/]")
        raise typer.Exit(code=1)

    parse_epub(epub_path, temp_dir)
    console.print("[bold green]Parse complete.[/] Run 'python main.py run' to translate.")


@app.command(name="run")
def run_cmd(
    config_path: str = typer.Option("config.json", "--config", "-c", help="Path to config.json"),
    temp_dir: str = typer.Option("temp", "--temp", "-t", help="Temporary working directory"),
):
    """Step 2: Translate extracted HTML files (requires parse first)."""
    html_dir = Path(temp_dir) / "html"
    if not html_dir.exists():
        console.print("[red]No HTML files found. Run 'python main.py parse' first.[/]")
        raise typer.Exit(code=1)

    config = load_config(config_path)
    translate_html_dir(html_dir, config,
                       progress_file=Path(temp_dir) / "progress.json",
                       metadata_file=Path(temp_dir) / "metadata.json")
    console.print("[bold green]Translation complete.[/] Run 'python main.py build' to build EPUB.")


@app.command(name="build")
def build_cmd(
    temp_dir: str = typer.Option("temp", "--temp", "-t", help="Temporary working directory"),
    output_dir: str = typer.Option("output", "--output", "-o", help="Output directory for bilingual EPUB"),
    cleanup: bool = typer.Option(False, "--cleanup", help="Remove temp directory after build"),
):
    """Step 3: Build bilingual EPUB. Use --cleanup to remove temp files."""
    result = build_epub(temp_dir, output_dir, cleanup=cleanup)


@app.command(name="translate")
def translate_cmd(
    epub_path: str = typer.Argument(..., help="Path to the English EPUB file"),
    config_path: str = typer.Option("config.json", "--config", "-c", help="Path to config.json"),
    output_dir: str = typer.Option("output", "--output", "-o", help="Output directory for bilingual EPUB"),
    temp_dir: str = typer.Option("temp", "--temp", "-t", help="Temporary working directory"),
    cleanup: bool = typer.Option(False, "--cleanup", help="Remove temp directory after build"),
):
    """Full pipeline: parse EPUB, translate HTML, and build bilingual EPUB."""
    if not Path(epub_path).exists():
        console.print(f"[red]File not found: {epub_path}[/]")
        raise typer.Exit(code=1)

    config = load_config(config_path)

    console.rule("[bold]Step 1/3: Parse EPUB[/]")
    parse_epub(epub_path, temp_dir)

    console.rule("[bold]Step 2/3: Translate Content[/]")
    html_dir = Path(temp_dir) / "html"
    translate_html_dir(html_dir, config,
                       progress_file=Path(temp_dir) / "progress.json",
                       metadata_file=Path(temp_dir) / "metadata.json")

    console.rule("[bold]Step 3/3: Build Bilingual EPUB[/]")
    result = build_epub(temp_dir, output_dir, cleanup=cleanup)

    console.rule("[bold green]Done![/]")
    console.print(f"[bold]Output:[/] {result}")


if __name__ == "__main__":
    app()
