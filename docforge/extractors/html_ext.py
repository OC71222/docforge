"""HTML extractor using BeautifulSoup."""

from __future__ import annotations

from pathlib import Path

from docforge.detector import DocumentFormat
from docforge.extractors.base import BaseExtractor, RawExtraction, RawTable, TextBlock
from docforge.registry import register

_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}


@register(DocumentFormat.HTML)
class HtmlExtractor(BaseExtractor):
    def extract(self, file_path: Path, **options: object) -> RawExtraction:
        from bs4 import BeautifulSoup

        html = file_path.read_text(encoding="utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")

        # Remove script, style, nav, header, footer
        for tag in soup.find_all(["script", "style", "nav", "header", "footer"]):
            tag.decompose()

        blocks: list[TextBlock] = []
        tables: list[RawTable] = []

        y = 0.0

        # Extract title from <title> tag
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else None

        # Walk the body (or whole document if no body)
        body = soup.find("body") or soup

        for element in body.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "table"]):
            tag_name = element.name

            if tag_name == "table":
                table = self._extract_table(element)
                if table:
                    tables.append(table)
                continue

            text = element.get_text(separator=" ", strip=True)
            if not text:
                continue

            is_heading = tag_name in _HEADING_TAGS
            heading_level = int(tag_name[1]) if is_heading else 0
            font_size = {1: 24, 2: 20, 3: 16, 4: 14, 5: 12, 6: 11}.get(heading_level, 11)

            blocks.append(TextBlock(
                text=text,
                page=0,
                x0=0,
                y0=y,
                x1=500,
                y1=y + font_size + 2,
                font_size=float(font_size),
                is_bold=is_heading,
                is_heading=is_heading,
                heading_level=heading_level,
            ))
            y += font_size + 6

        # Extract metadata from meta tags
        metadata: dict = {"title": title, "page_count": 1}
        for meta in soup.find_all("meta"):
            name = (meta.get("name") or "").lower()
            content = meta.get("content", "")
            if name == "author":
                metadata["author"] = content
            elif name == "description":
                metadata["description"] = content

        return RawExtraction(
            text_blocks=blocks,
            tables=tables,
            images=[],
            metadata=metadata,
            page_count=1,
        )

    def _extract_table(self, table_element) -> RawTable | None:
        """Extract a table from a <table> element."""
        rows_data: list[list[str]] = []

        for tr in table_element.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            row = [cell.get_text(strip=True) for cell in cells]
            if row:
                rows_data.append(row)

        if not rows_data:
            return None

        headers = rows_data[0]
        data_rows = rows_data[1:] if len(rows_data) > 1 else []

        return RawTable(headers=headers, rows=data_rows, page=0)
