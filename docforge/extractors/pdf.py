"""PDF extractor using PyMuPDF — handles digital and scanned PDFs."""

from __future__ import annotations

import statistics
from pathlib import Path

import fitz

from docforge.detector import DocumentFormat
from docforge.extractors.base import BaseExtractor, RawExtraction, RawImage, RawTable, TextBlock
from docforge.registry import register


@register(DocumentFormat.PDF)
class PdfExtractor(BaseExtractor):
    def extract(self, file_path: Path, **options: object) -> RawExtraction:
        extract_images = bool(options.get("extract_images", False))
        pages_filter: list[int] | None = options.get("pages", None)  # type: ignore[assignment]
        ocr_engine: str = str(options.get("ocr_engine", "tesseract"))
        hybrid: bool = bool(options.get("hybrid", False))

        doc = fitz.open(str(file_path))
        try:
            all_blocks: list[TextBlock] = []
            all_tables: list[RawTable] = []
            all_images: list[RawImage] = []
            ocr_pages: set[int] = set()

            for page_num in range(len(doc)):
                if pages_filter and (page_num + 1) not in pages_filter:
                    continue

                page = doc[page_num]

                # Check if page is scanned (image-based with little/no text)
                page_text = page.get_text()
                page_images = page.get_images()

                from docforge.utils.ocr import is_scanned_page, needs_hybrid_extraction

                if is_scanned_page(page_text, len(page_images)):
                    # Scanned page — render to image and run OCR
                    blocks = self._ocr_page(page, page_num, ocr_engine)
                    ocr_pages.add(page_num)
                elif hybrid and needs_hybrid_extraction(page_text, len(page_images)):
                    # Form page — run both digital extraction and OCR, merge
                    blocks = self._hybrid_extract_page(page, page_num, ocr_engine)
                else:
                    # Digital page — extract text directly
                    blocks = self._extract_text_blocks(page, page_num)

                all_blocks.extend(blocks)

                # Table detection
                from docforge.utils.table_detect import detect_tables_from_pdf_page

                tables = detect_tables_from_pdf_page(page, page_num)
                all_tables.extend(tables)

                # Image extraction
                if extract_images:
                    images = self._extract_images(doc, page, page_num)
                    all_images.extend(images)

            # Detect headings across all blocks
            self._detect_headings(all_blocks)

            # Order blocks for reading — skip column detection for OCR pages
            # (OCR already returns blocks in reading order)
            all_blocks = self._order_blocks(all_blocks, ocr_pages)

            metadata = self._extract_metadata(doc)

            return RawExtraction(
                text_blocks=all_blocks,
                tables=all_tables,
                images=all_images,
                metadata=metadata,
                page_count=len(doc),
            )
        finally:
            doc.close()

    def _ocr_page(
        self, page: fitz.Page, page_num: int, ocr_engine: str
    ) -> list[TextBlock]:
        """Render a scanned page to image and run OCR."""
        from docforge.utils.ocr import run_ocr

        pix = page.get_pixmap(dpi=300)
        image_bytes = pix.tobytes("png")
        return run_ocr(image_bytes, page_num=page_num, engine=ocr_engine)

    def _hybrid_extract_page(
        self, page: fitz.Page, page_num: int, ocr_engine: str
    ) -> list[TextBlock]:
        """Run both digital extraction and OCR, then merge results."""
        from docforge.utils.ocr import merge_hybrid_blocks, normalize_ocr_coords, run_ocr

        digital_blocks = self._extract_text_blocks(page, page_num)

        dpi = 300
        pix = page.get_pixmap(dpi=dpi)
        image_bytes = pix.tobytes("png")
        ocr_blocks = run_ocr(image_bytes, page_num=page_num, engine=ocr_engine)

        rect = page.rect
        ocr_blocks = normalize_ocr_coords(
            ocr_blocks, rect.width, rect.height, dpi=dpi
        )

        return merge_hybrid_blocks(digital_blocks, ocr_blocks)

    def _extract_text_blocks(self, page: fitz.Page, page_num: int) -> list[TextBlock]:
        """Extract text blocks with position and font info from a page."""
        blocks: list[TextBlock] = []
        text_dict = page.get_text("dict")

        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:  # text block only
                continue

            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue

                # Merge spans in a line into a single TextBlock
                text_parts = []
                total_size = 0.0
                any_bold = False

                for span in spans:
                    text = span.get("text", "").strip()
                    if not text:
                        continue
                    text_parts.append(text)
                    total_size += span.get("size", 0)
                    flags = span.get("flags", 0)
                    if flags & 2 ** 4:  # bold flag
                        any_bold = True

                if not text_parts:
                    continue

                merged_text = " ".join(text_parts)
                avg_size = total_size / len(text_parts) if text_parts else 0
                bbox = line.get("bbox", (0, 0, 0, 0))

                blocks.append(TextBlock(
                    text=merged_text,
                    page=page_num,
                    x0=bbox[0],
                    y0=bbox[1],
                    x1=bbox[2],
                    y1=bbox[3],
                    font_size=avg_size,
                    is_bold=any_bold,
                ))

        return blocks

    def _detect_headings(self, blocks: list[TextBlock]) -> None:
        """Mark blocks as headings based on font size relative to median."""
        if not blocks:
            return

        sizes = [b.font_size for b in blocks if b.font_size > 0]
        if not sizes:
            return

        median_size = statistics.median(sizes)
        max_size = max(sizes)

        for block in blocks:
            if block.font_size <= 0:
                continue

            ratio = block.font_size / median_size if median_size > 0 else 1.0

            if ratio > 1.8 or block.font_size == max_size:
                block.is_heading = True
                block.heading_level = 1
            elif ratio > 1.4 or (block.is_bold and ratio > 1.2):
                block.is_heading = True
                block.heading_level = 2
            elif block.is_bold and ratio > 1.05:
                block.is_heading = True
                block.heading_level = 3

    def _order_blocks(
        self, blocks: list[TextBlock], ocr_pages: set[int] | None = None
    ) -> list[TextBlock]:
        """Order blocks by reading order: detect columns, read top-to-bottom within each."""
        if not blocks:
            return blocks

        ocr_pages = ocr_pages or set()

        # Group by page
        pages: dict[int, list[TextBlock]] = {}
        for b in blocks:
            pages.setdefault(b.page, []).append(b)

        ordered: list[TextBlock] = []
        for page_num in sorted(pages.keys()):
            page_blocks = pages[page_num]
            if page_num in ocr_pages:
                # OCR pages: already in reading order (y-sorted), just keep as-is
                ordered.extend(sorted(page_blocks, key=lambda b: (b.y0, b.x0)))
            else:
                ordered.extend(self._order_page_blocks(page_blocks))

        return ordered

    def _order_page_blocks(self, blocks: list[TextBlock]) -> list[TextBlock]:
        """Order blocks within a single page using column detection."""
        if len(blocks) <= 1:
            return blocks

        # Find column boundaries by clustering x0 values
        columns = self._detect_columns(blocks)

        if len(columns) <= 1:
            # Single column: sort top-to-bottom
            return sorted(blocks, key=lambda b: (b.y0, b.x0))

        # Multi-column: sort by column left-to-right, then top-to-bottom within each
        result: list[TextBlock] = []
        for col_blocks in columns:
            col_blocks.sort(key=lambda b: b.y0)
            result.extend(col_blocks)

        return result

    def _detect_columns(self, blocks: list[TextBlock]) -> list[list[TextBlock]]:
        """Detect columns by clustering blocks by x-coordinate gaps."""
        if not blocks:
            return []

        # Sort by x0
        sorted_blocks = sorted(blocks, key=lambda b: b.x0)

        # Look for a significant gap in x-coordinates
        # Use the page width to determine if there's a multi-column layout
        x_values = sorted(set(round(b.x0) for b in sorted_blocks))

        if len(x_values) < 2:
            return [sorted_blocks]

        # Find the largest gap between distinct x-start positions
        gaps: list[tuple[float, float]] = []
        for i in range(len(x_values) - 1):
            gap = x_values[i + 1] - x_values[i]
            gaps.append((gap, (x_values[i] + x_values[i + 1]) / 2))

        if not gaps:
            return [sorted_blocks]

        max_gap, split_x = max(gaps, key=lambda g: g[0])

        # Only split if gap is significant (> 20% of page-width range)
        x_range = x_values[-1] - x_values[0]
        if x_range == 0 or max_gap / x_range < 0.15:
            return [sorted_blocks]

        # Split into columns
        left = [b for b in sorted_blocks if (b.x0 + b.x1) / 2 < split_x]
        right = [b for b in sorted_blocks if (b.x0 + b.x1) / 2 >= split_x]

        columns = []
        if left:
            columns.append(left)
        if right:
            columns.append(right)

        return columns if len(columns) > 1 else [sorted_blocks]

    def _extract_images(
        self, doc: fitz.Document, page: fitz.Page, page_num: int
    ) -> list[RawImage]:
        """Extract embedded images from a page."""
        images: list[RawImage] = []
        for img_info in page.get_images():
            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
                if base_image:
                    images.append(RawImage(
                        data=base_image["image"],
                        format=base_image.get("ext", "png"),
                        page=page_num,
                        width=base_image.get("width", 0),
                        height=base_image.get("height", 0),
                    ))
            except Exception:
                continue  # Skip unextractable images
        return images

    def _extract_metadata(self, doc: fitz.Document) -> dict:
        """Extract document metadata."""
        meta = doc.metadata or {}
        return {
            "title": meta.get("title") or None,
            "author": meta.get("author") or None,
            "created_date": meta.get("creationDate") or None,
            "modified_date": meta.get("modDate") or None,
            "producer": meta.get("producer") or None,
            "page_count": len(doc),
        }
