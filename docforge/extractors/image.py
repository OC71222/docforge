"""Image extractor — OCR-based extraction for standalone images."""

from __future__ import annotations

from pathlib import Path

from docforge.detector import DocumentFormat
from docforge.extractors.base import BaseExtractor, RawExtraction, TextBlock
from docforge.registry import register


@register(DocumentFormat.IMAGE)
class ImageExtractor(BaseExtractor):
    def extract(self, file_path: Path, **options: object) -> RawExtraction:
        ocr_engine: str = str(options.get("ocr_engine", "tesseract"))

        image_bytes = file_path.read_bytes()

        from docforge.utils.ocr import run_ocr

        blocks = run_ocr(image_bytes, page_num=0, engine=ocr_engine)

        return RawExtraction(
            text_blocks=blocks,
            tables=[],
            images=[],
            metadata={"page_count": 1},
            page_count=1,
        )
