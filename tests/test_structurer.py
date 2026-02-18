"""Tests for the structurer module."""

from __future__ import annotations

from docforge.extractors.base import RawExtraction, RawTable, TextBlock
from docforge.structurer import structure


class TestStructurer:
    def test_empty_extraction(self) -> None:
        raw = RawExtraction()
        result = structure(raw)
        assert result.content == ""
        assert result.markdown == ""
        assert result.sections == []
        assert result.tables == []

    def test_plain_text_blocks(self) -> None:
        raw = RawExtraction(
            text_blocks=[
                TextBlock(text="Hello world", page=0),
                TextBlock(text="Second paragraph", page=0),
            ],
            page_count=1,
        )
        result = structure(raw)
        assert "Hello world" in result.content
        assert "Second paragraph" in result.content

    def test_heading_creates_sections(self) -> None:
        raw = RawExtraction(
            text_blocks=[
                TextBlock(text="Title", page=0, is_heading=True, heading_level=1, font_size=24),
                TextBlock(text="Some content here.", page=0, font_size=11),
                TextBlock(text="Subtitle", page=0, is_heading=True, heading_level=2, font_size=16),
                TextBlock(text="More content.", page=0, font_size=11),
            ],
            page_count=1,
        )
        result = structure(raw)
        assert len(result.sections) >= 1
        assert result.sections[0].heading == "Title"
        assert result.sections[0].level == 1

    def test_nested_sections(self) -> None:
        raw = RawExtraction(
            text_blocks=[
                TextBlock(text="H1", page=0, is_heading=True, heading_level=1, font_size=24),
                TextBlock(text="Body 1", page=0, font_size=11),
                TextBlock(text="H2", page=0, is_heading=True, heading_level=2, font_size=16),
                TextBlock(text="Body 2", page=0, font_size=11),
            ],
            page_count=1,
        )
        result = structure(raw)
        assert len(result.sections) == 1
        assert result.sections[0].heading == "H1"
        assert len(result.sections[0].children) == 1
        assert result.sections[0].children[0].heading == "H2"

    def test_markdown_headings(self) -> None:
        raw = RawExtraction(
            text_blocks=[
                TextBlock(text="Title", page=0, is_heading=True, heading_level=1),
                TextBlock(text="Body text", page=0),
            ],
            page_count=1,
        )
        result = structure(raw)
        assert "# Title" in result.markdown
        assert "Body text" in result.markdown

    def test_table_in_output(self) -> None:
        raw = RawExtraction(
            text_blocks=[TextBlock(text="Before table", page=0)],
            tables=[
                RawTable(
                    headers=["Name", "Value"],
                    rows=[["A", "1"], ["B", "2"]],
                    page=0,
                ),
            ],
            page_count=1,
        )
        result = structure(raw)
        assert len(result.tables) == 1
        assert result.tables[0].headers == ["Name", "Value"]
        assert len(result.tables[0].rows) == 2

    def test_table_markdown(self) -> None:
        raw = RawExtraction(
            tables=[
                RawTable(
                    headers=["Col1", "Col2"],
                    rows=[["a", "b"]],
                    page=0,
                ),
            ],
            page_count=1,
        )
        result = structure(raw)
        assert "| Col1 | Col2 |" in result.markdown
        assert "| a | b |" in result.markdown

    def test_multi_page(self) -> None:
        raw = RawExtraction(
            text_blocks=[
                TextBlock(text="Page 1 content", page=0),
                TextBlock(text="Page 2 content", page=1),
            ],
            page_count=2,
        )
        result = structure(raw)
        assert len(result.pages) == 2
        assert result.pages[0].number == 1
        assert result.pages[1].number == 2
        assert "Page 1" in result.pages[0].content
        assert "Page 2" in result.pages[1].content

    def test_word_count(self) -> None:
        raw = RawExtraction(
            text_blocks=[TextBlock(text="one two three four five", page=0)],
            page_count=1,
        )
        result = structure(raw)
        assert result.metadata.word_count == 5

    def test_to_json(self) -> None:
        raw = RawExtraction(
            text_blocks=[TextBlock(text="Hello", page=0)],
            page_count=1,
        )
        result = structure(raw)
        json_str = result.to_json()
        assert '"content"' in json_str
        assert "Hello" in json_str

    def test_to_dict(self) -> None:
        raw = RawExtraction(
            text_blocks=[TextBlock(text="Hello", page=0)],
            page_count=1,
        )
        result = structure(raw)
        d = result.to_dict()
        assert isinstance(d, dict)
        assert d["content"] == "Hello"
