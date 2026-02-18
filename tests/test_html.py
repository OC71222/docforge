"""Tests for HTML extraction."""

from __future__ import annotations

from pathlib import Path

import docforge
from docforge.extractors.html_ext import HtmlExtractor

FIXTURES = Path(__file__).parent / "fixtures"


class TestHtmlExtraction:
    def test_text_extraction(self) -> None:
        result = docforge.parse(FIXTURES / "sample.html")
        assert "first paragraph" in result.content.lower()
        assert "section one" in result.content.lower()
        assert "section two" in result.content.lower()

    def test_heading_detection(self) -> None:
        result = docforge.parse(FIXTURES / "sample.html")

        def collect_headings(sections):
            for s in sections:
                if s.heading:
                    yield s.heading.lower()
                yield from collect_headings(s.children)

        headings = list(collect_headings(result.sections))
        assert any("main heading" in h for h in headings)

    def test_table_extraction(self) -> None:
        result = docforge.parse(FIXTURES / "sample.html")
        assert len(result.tables) > 0
        table = result.tables[0]
        assert "Name" in table.headers
        assert "Value" in table.headers

    def test_metadata(self) -> None:
        result = docforge.parse(FIXTURES / "sample.html")
        assert result.metadata.title == "Sample Document"
        assert result.source_format == "html"

    def test_markdown_output(self) -> None:
        result = docforge.parse(FIXTURES / "sample.html")
        assert result.markdown
        assert "#" in result.markdown


class TestHtmlExtractorDirect:
    def test_extract_raw(self) -> None:
        extractor = HtmlExtractor()
        raw = extractor.extract(FIXTURES / "sample.html")
        assert len(raw.text_blocks) > 0
        assert raw.page_count == 1
