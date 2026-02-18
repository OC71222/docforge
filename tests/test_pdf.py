"""Tests for PDF extraction."""

from __future__ import annotations

from pathlib import Path

import docforge
from docforge.extractors.pdf import PdfExtractor

FIXTURES = Path(__file__).parent / "fixtures"


class TestPdfExtraction:
    def test_simple_text_extraction(self) -> None:
        result = docforge.parse(FIXTURES / "simple.pdf")
        assert "introduction" in result.content.lower()
        assert "methods" in result.content.lower()
        assert result.source_format == "pdf"

    def test_heading_detection(self) -> None:
        result = docforge.parse(FIXTURES / "simple.pdf")

        # Collect all headings recursively
        def collect_headings(sections):
            for s in sections:
                if s.heading:
                    yield s.heading.lower()
                yield from collect_headings(s.children)

        heading_texts = list(collect_headings(result.sections))
        assert any("document title" in h for h in heading_texts)
        assert any("introduction" in h or "methods" in h for h in heading_texts)

    def test_section_tree(self) -> None:
        result = docforge.parse(FIXTURES / "simple.pdf")
        # Should have sections
        assert len(result.sections) > 0

    def test_metadata(self) -> None:
        result = docforge.parse(FIXTURES / "simple.pdf")
        assert result.metadata.page_count == 1
        assert result.metadata.word_count is not None
        assert result.metadata.word_count > 0

    def test_markdown_output(self) -> None:
        result = docforge.parse(FIXTURES / "simple.pdf")
        assert result.markdown
        # Should contain heading markers
        assert "#" in result.markdown

    def test_pages(self) -> None:
        result = docforge.parse(FIXTURES / "simple.pdf")
        assert len(result.pages) >= 1
        assert result.pages[0].number == 1
        assert result.pages[0].content

    def test_parse_time(self) -> None:
        result = docforge.parse(FIXTURES / "simple.pdf")
        assert result.parse_time_seconds > 0
        assert result.parse_time_seconds < 10  # sanity check


class TestTableExtraction:
    def test_table_detected(self) -> None:
        result = docforge.parse(FIXTURES / "tables.pdf")
        assert len(result.tables) > 0

    def test_table_headers(self) -> None:
        result = docforge.parse(FIXTURES / "tables.pdf")
        if result.tables:
            table = result.tables[0]
            header_text = " ".join(table.headers).lower()
            assert "quarter" in header_text or "revenue" in header_text

    def test_table_rows(self) -> None:
        result = docforge.parse(FIXTURES / "tables.pdf")
        if result.tables:
            table = result.tables[0]
            assert len(table.rows) >= 2

    def test_table_in_markdown(self) -> None:
        result = docforge.parse(FIXTURES / "tables.pdf")
        # Markdown should contain table syntax
        assert "|" in result.markdown


class TestMultiColumn:
    def test_multicolumn_extraction(self) -> None:
        result = docforge.parse(FIXTURES / "multicolumn.pdf")
        assert "left" in result.content.lower() or "right" in result.content.lower()

    def test_reading_order(self) -> None:
        result = docforge.parse(FIXTURES / "multicolumn.pdf")
        content = result.content.lower()
        # Left column content should appear before right column content
        left_pos = content.find("left column") if "left column" in content else -1
        right_pos = content.find("right column") if "right column" in content else -1
        if left_pos >= 0 and right_pos >= 0:
            assert left_pos < right_pos


class TestPdfExtractorDirect:
    def test_extract_raw(self) -> None:
        extractor = PdfExtractor()
        raw = extractor.extract(FIXTURES / "simple.pdf")
        assert raw.page_count == 1
        assert len(raw.text_blocks) > 0
        assert raw.metadata.get("page_count") == 1

    def test_page_filter(self) -> None:
        extractor = PdfExtractor()
        raw = extractor.extract(FIXTURES / "simple.pdf", pages=[1])
        assert len(raw.text_blocks) > 0

    def test_page_filter_empty(self) -> None:
        extractor = PdfExtractor()
        raw = extractor.extract(FIXTURES / "simple.pdf", pages=[99])
        assert len(raw.text_blocks) == 0


class TestHybridExtraction:
    def test_hybrid_flag_passes_through(self) -> None:
        """Hybrid flag should not error on a normal digital PDF."""
        extractor = PdfExtractor()
        raw = extractor.extract(FIXTURES / "simple.pdf", hybrid=True)
        assert len(raw.text_blocks) > 0

    def test_hybrid_same_as_digital_on_pure_text(self) -> None:
        """On a pure-digital PDF with no form pages, hybrid produces same text."""
        extractor = PdfExtractor()
        normal = extractor.extract(FIXTURES / "simple.pdf")
        hybrid = extractor.extract(FIXTURES / "simple.pdf", hybrid=True)
        normal_texts = [b.text for b in normal.text_blocks]
        hybrid_texts = [b.text for b in hybrid.text_blocks]
        assert normal_texts == hybrid_texts
