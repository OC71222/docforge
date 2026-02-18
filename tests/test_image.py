"""Tests for image extraction."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"

try:
    import pytesseract as _pt  # noqa: F401
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False

pytestmark = pytest.mark.skipif(not HAS_TESSERACT, reason="pytesseract not installed")


class TestImageExtraction:
    def test_text_extraction(self) -> None:
        import docforge
        result = docforge.parse(FIXTURES / "sample.png")
        content = result.content.lower()
        assert "hello" in content or "world" in content

    def test_source_format(self) -> None:
        import docforge
        result = docforge.parse(FIXTURES / "sample.png")
        assert result.source_format == "image"

    def test_page_count(self) -> None:
        import docforge
        result = docforge.parse(FIXTURES / "sample.png")
        assert result.metadata.page_count == 1


class TestImageExtractorDirect:
    def test_extract_raw(self) -> None:
        from docforge.extractors.image import ImageExtractor
        extractor = ImageExtractor()
        raw = extractor.extract(FIXTURES / "sample.png")
        assert raw.page_count == 1
        assert len(raw.text_blocks) > 0
