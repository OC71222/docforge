"""Tests for email extraction."""

from __future__ import annotations

from pathlib import Path

import docforge
from docforge.extractors.email_ext import EmlExtractor

FIXTURES = Path(__file__).parent / "fixtures"


class TestEmlExtraction:
    def test_text_extraction(self) -> None:
        result = docforge.parse(FIXTURES / "sample.eml")
        assert "body of the test email" in result.content.lower()

    def test_subject_as_heading(self) -> None:
        result = docforge.parse(FIXTURES / "sample.eml")
        assert "Test Email Subject" in result.content

    def test_headers_in_content(self) -> None:
        result = docforge.parse(FIXTURES / "sample.eml")
        assert "sender@example.com" in result.content
        assert "recipient@example.com" in result.content

    def test_metadata(self) -> None:
        result = docforge.parse(FIXTURES / "sample.eml")
        assert result.metadata.title == "Test Email Subject"
        assert result.source_format == "eml"

    def test_markdown_output(self) -> None:
        result = docforge.parse(FIXTURES / "sample.eml")
        assert result.markdown
        assert "Test Email Subject" in result.markdown


class TestEmlExtractorDirect:
    def test_extract_raw(self) -> None:
        extractor = EmlExtractor()
        raw = extractor.extract(FIXTURES / "sample.eml")
        assert len(raw.text_blocks) > 0
        assert raw.page_count == 1
