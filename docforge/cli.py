"""Click-based CLI for DocForge."""

from __future__ import annotations

from pathlib import Path

import click


@click.group()
@click.version_option(package_name="docforge")
def main() -> None:
    """DocForge — Universal document parser for LLMs."""


@main.command()
@click.argument("source")
@click.option(
    "--format", "-f",
    "output_format",
    type=click.Choice(["markdown", "json"]),
    default="markdown",
    help="Output format.",
)
@click.option("--output", "-o", type=click.Path(), default=None, help="Output file path.")
@click.option("--ocr-engine", type=click.Choice(["tesseract", "easyocr"]), default="tesseract")
@click.option("--pages", type=str, default=None, help="Page range, e.g. '1-5' or '1,3,5'.")
@click.option("--extract-images", is_flag=True, help="Extract embedded images.")
@click.option("--hybrid", is_flag=True, help="Run digital + OCR on form pages to capture handwriting.")
def parse(
    source: str,
    output_format: str,
    output: str | None,
    ocr_engine: str,
    pages: str | None,
    extract_images: bool,
    hybrid: bool,
) -> None:
    """Parse a document and output structured content."""
    from docforge.parser import parse as do_parse

    page_list = _parse_pages(pages) if pages else None

    result = do_parse(
        source,
        ocr_engine=ocr_engine,
        extract_images=extract_images,
        pages=page_list,
        hybrid=hybrid,
    )

    if output_format == "json":
        text = result.to_json()
    else:
        text = result.markdown

    if output:
        Path(output).write_text(text, encoding="utf-8")
        click.echo(f"Written to {output}")
    else:
        click.echo(text)


@main.command()
@click.argument("directory")
@click.option("--compare", type=str, default=None, help="Compare against another tool.")
def benchmark(directory: str, compare: str | None) -> None:
    """Run benchmarks on a directory of documents."""
    click.echo(f"Benchmarking {directory}...")
    click.echo("Not yet implemented.")


def _parse_pages(pages_str: str) -> list[int]:
    """Parse page range string like '1-5' or '1,3,5' into list of ints."""
    result: list[int] = []
    for part in pages_str.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            result.extend(range(int(start), int(end) + 1))
        else:
            result.append(int(part))
    return result
