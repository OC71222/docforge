"""Main parse() orchestration logic."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

from docforge.detector import DocumentFormat, detect
from docforge.models import ParseResult
from docforge.registry import UnsupportedFormatError, get_extractor
from docforge.structurer import structure


def parse(
    source: str | bytes | Path,
    *,
    filename: str | None = None,
    ocr_engine: str = "tesseract",
    extract_images: bool = False,
    pages: list[int] | None = None,
    output_format: str = "both",
    hybrid: bool = False,
) -> ParseResult:
    """Parse a document into structured data.

    Args:
        source: File path, URL, or raw bytes.
        filename: Required when source is bytes (used for format detection).
        ocr_engine: OCR engine to use ("tesseract" or "easyocr").
        extract_images: Whether to extract embedded images.
        pages: Specific page numbers to extract (None = all).
        output_format: Output format ("markdown", "json", or "both").
        hybrid: Run both digital + OCR on form-like pages and merge.

    Returns:
        ParseResult with structured content.
    """
    start_time = time.monotonic()

    file_path = _resolve_source(source, filename)

    try:
        fmt = detect(file_path)
        if fmt == DocumentFormat.UNKNOWN:
            raise UnsupportedFormatError(f"Cannot detect format of: {file_path}")

        extractor = get_extractor(fmt)
        raw = extractor.extract(
            file_path,
            ocr_engine=ocr_engine,
            extract_images=extract_images,
            pages=pages,
            hybrid=hybrid,
        )

        result = structure(raw)
        result.source_format = fmt.value
        result.parse_time_seconds = round(time.monotonic() - start_time, 3)
        return result
    finally:
        # Clean up temp files created from bytes/URL input
        if isinstance(source, (str, bytes)) and _is_temp(file_path):
            file_path.unlink(missing_ok=True)


def _resolve_source(source: str | bytes | Path, filename: str | None) -> Path:
    """Resolve source to a local file path."""
    if isinstance(source, bytes):
        if not filename:
            raise ValueError("filename is required when source is bytes")
        suffix = Path(filename).suffix
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        tmp.write(source)
        tmp.close()
        return Path(tmp.name)

    if isinstance(source, str):
        if source.startswith(("http://", "https://")):
            from docforge.utils.download import download_to_temp

            return download_to_temp(source)
        return Path(source)

    return Path(source)


def _is_temp(path: Path) -> bool:
    """Check if a path is in the system temp directory."""
    try:
        return str(path).startswith(tempfile.gettempdir())
    except Exception:
        return False
