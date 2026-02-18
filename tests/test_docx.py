"""Tests for DOCX extraction."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"

try:
    from docx import Document as _Doc  # noqa: F401
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

pytestmark = pytest.mark.skipif(not HAS_DOCX, reason="python-docx not installed")


class TestDocxExtraction:
    def test_text_extraction(self) -> None:
        import docforge
        result = docforge.parse(FIXTURES / "sample.docx")
        assert "introduction paragraph" in result.content.lower()
        assert "methods" in result.content.lower()

    def test_heading_detection(self) -> None:
        import docforge
        result = docforge.parse(FIXTURES / "sample.docx")

        def collect_headings(sections):
            for s in sections:
                if s.heading:
                    yield s.heading.lower()
                yield from collect_headings(s.children)

        headings = list(collect_headings(result.sections))
        assert any("document title" in h for h in headings)
        assert any("methods" in h for h in headings)

    def test_table_extraction(self) -> None:
        import docforge
        result = docforge.parse(FIXTURES / "sample.docx")
        assert len(result.tables) > 0
        table = result.tables[0]
        assert "Name" in table.headers
        assert "Score" in table.headers

    def test_metadata(self) -> None:
        import docforge
        result = docforge.parse(FIXTURES / "sample.docx")
        assert result.metadata.title == "Sample DOCX"
        assert result.source_format == "docx"

    def test_markdown_output(self) -> None:
        import docforge
        result = docforge.parse(FIXTURES / "sample.docx")
        assert result.markdown
        assert "#" in result.markdown


class TestDocxExtractorDirect:
    def test_extract_raw(self) -> None:
        from docforge.extractors.docx_ext import DocxExtractor
        extractor = DocxExtractor()
        raw = extractor.extract(FIXTURES / "sample.docx")
        assert len(raw.text_blocks) > 0
        assert raw.page_count == 1
