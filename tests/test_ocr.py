"""Unit tests for hybrid extraction helpers in docforge.utils.ocr."""

from __future__ import annotations

from docforge.extractors.base import TextBlock
from docforge.utils.ocr import (
    _overlap_ratio,
    merge_hybrid_blocks,
    needs_hybrid_extraction,
    normalize_ocr_coords,
)


class TestNeedsHybridExtraction:
    def test_blank_page(self) -> None:
        assert needs_hybrid_extraction("", 1) is False

    def test_too_little_text(self) -> None:
        assert needs_hybrid_extraction("Hello", 1) is False

    def test_prose_page(self) -> None:
        # Long paragraph — not form-like even though it has images
        prose = "This is a long paragraph of prose that contains many words. " * 20
        assert needs_hybrid_extraction(prose, 1) is False

    def test_no_images(self) -> None:
        form = "Last Name:\nFirst Name:\nCity:\nState:\nZip:\n"
        assert needs_hybrid_extraction(form, 0) is False

    def test_form_page(self) -> None:
        form = "\n".join([
            "Last Name:",
            "First Name:",
            "Middle Name:",
            "Date of Birth:",
            "City of Birth:",
            "State:",
            "Zip Code:",
            "Eye Color:",
            "Height:",
            "Weight:",
        ])
        assert needs_hybrid_extraction(form, 1) is True

    def test_too_much_text(self) -> None:
        # Over 2000 chars — not a form
        form = ("Label:\n" * 500)
        assert needs_hybrid_extraction(form, 1) is False


class TestOverlapRatio:
    def test_no_overlap(self) -> None:
        a = TextBlock(text="a", x0=0, y0=0, x1=10, y1=10)
        b = TextBlock(text="b", x0=20, y0=20, x1=30, y1=30)
        assert _overlap_ratio(a, b) == 0.0

    def test_full_overlap(self) -> None:
        a = TextBlock(text="a", x0=0, y0=0, x1=10, y1=10)
        b = TextBlock(text="b", x0=0, y0=0, x1=10, y1=10)
        assert _overlap_ratio(a, b) == 1.0

    def test_partial_overlap(self) -> None:
        a = TextBlock(text="a", x0=0, y0=0, x1=10, y1=10)
        b = TextBlock(text="b", x0=5, y0=0, x1=15, y1=10)
        ratio = _overlap_ratio(a, b)
        assert 0.49 < ratio < 0.51  # 50% overlap

    def test_zero_area_block(self) -> None:
        a = TextBlock(text="a", x0=5, y0=5, x1=5, y1=5)
        b = TextBlock(text="b", x0=0, y0=0, x1=10, y1=10)
        assert _overlap_ratio(a, b) == 0.0


class TestMergeHybridBlocks:
    def test_no_overlap_keeps_all(self) -> None:
        digital = [TextBlock(text="Label:", page=0, x0=0, y0=0, x1=50, y1=10)]
        ocr = [TextBlock(text="Epstein", page=0, x0=100, y0=0, x1=200, y1=10, source="ocr")]
        merged = merge_hybrid_blocks(digital, ocr)
        texts = [b.text for b in merged]
        assert "Label:" in texts
        assert "Epstein" in texts

    def test_full_overlap_discards_ocr_dup(self) -> None:
        digital = [TextBlock(text="Last Name:", page=0, x0=10, y0=10, x1=100, y1=25)]
        ocr = [TextBlock(text="Last Name", page=0, x0=10, y0=10, x1=100, y1=25, source="ocr")]
        merged = merge_hybrid_blocks(digital, ocr)
        assert len(merged) == 1
        assert merged[0].text == "Last Name:"

    def test_mixed_keeps_handwritten(self) -> None:
        digital = [
            TextBlock(text="Last Name:", page=0, x0=10, y0=10, x1=100, y1=25),
            TextBlock(text="First Name:", page=0, x0=10, y0=30, x1=100, y1=45),
        ]
        ocr = [
            TextBlock(text="Last Name", page=0, x0=10, y0=10, x1=100, y1=25, source="ocr"),
            TextBlock(text="Epstein", page=0, x0=110, y0=10, x1=200, y1=25, source="ocr"),
            TextBlock(text="Jeffrey", page=0, x0=110, y0=30, x1=200, y1=45, source="ocr"),
        ]
        merged = merge_hybrid_blocks(digital, ocr)
        texts = [b.text for b in merged]
        assert "Last Name:" in texts
        assert "First Name:" in texts
        assert "Epstein" in texts
        assert "Jeffrey" in texts
        # "Last Name" OCR dup should be discarded
        assert texts.count("Last Name:") == 1
        assert "Last Name" not in [t for t in texts if t != "Last Name:"]

    def test_empty_inputs(self) -> None:
        assert merge_hybrid_blocks([], []) == []
        digital = [TextBlock(text="x", page=0, x0=0, y0=0, x1=10, y1=10)]
        assert merge_hybrid_blocks(digital, []) == digital

    def test_sorted_by_position(self) -> None:
        digital = [TextBlock(text="bottom", page=0, x0=0, y0=100, x1=50, y1=110)]
        ocr = [TextBlock(text="top", page=0, x0=0, y0=0, x1=50, y1=10, source="ocr")]
        merged = merge_hybrid_blocks(digital, ocr)
        assert merged[0].text == "top"
        assert merged[1].text == "bottom"


class TestNormalizeOcrCoords:
    def test_scaling(self) -> None:
        # Page is 612x792 pts (US Letter). At 300 DPI the image is
        # 612*300/72 = 2550 px wide, 792*300/72 = 3300 px tall.
        # scale factor = 72/300 = 0.24
        blocks = [TextBlock(text="x", x0=2550, y0=3300, x1=2550, y1=3300)]
        result = normalize_ocr_coords(blocks, 612.0, 792.0, dpi=300)
        # After scaling: 2550 * 0.24 = 612, 3300 * 0.24 = 792
        assert abs(result[0].x0 - 612.0) < 0.1
        assert abs(result[0].y0 - 792.0) < 0.1

    def test_empty(self) -> None:
        assert normalize_ocr_coords([], 612.0, 792.0) == []
