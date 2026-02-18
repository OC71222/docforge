"""Converts RawExtraction into final ParseResult."""

from __future__ import annotations

from docforge.extractors.base import RawExtraction, RawTable, TextBlock
from docforge.models import (
    ExtractedImage,
    ExtractedTable,
    Metadata,
    Page,
    ParseResult,
    Section,
)


def structure(raw: RawExtraction) -> ParseResult:
    """Convert raw extraction into a structured ParseResult."""
    sections = _build_sections(raw.text_blocks)
    tables = _convert_tables(raw.tables)
    images = _convert_images(raw.images)
    pages = _build_pages(raw.text_blocks, raw.tables, raw.images)
    markdown = _generate_markdown(raw.text_blocks, raw.tables)
    content = _generate_plain_text(raw.text_blocks)
    metadata = _build_metadata(raw.metadata, content)

    return ParseResult(
        content=content,
        markdown=markdown,
        sections=sections,
        tables=tables,
        metadata=metadata,
        pages=pages,
        images=images,
    )


def _build_sections(blocks: list[TextBlock]) -> list[Section]:
    """Build a section tree from text blocks with heading detection."""
    if not blocks:
        return []

    # Create a flat list of sections, then nest them
    root_sections: list[Section] = []
    stack: list[Section] = []  # Stack of (section, level) for nesting

    current_content_parts: list[str] = []

    def flush_content() -> None:
        if current_content_parts and stack:
            text = "\n".join(current_content_parts).strip()
            if text:
                if stack[-1].content:
                    stack[-1].content += "\n" + text
                else:
                    stack[-1].content = text
            current_content_parts.clear()

    for block in blocks:
        if block.is_heading and block.heading_level > 0:
            flush_content()

            new_section = Section(
                heading=block.text,
                level=block.heading_level,
            )

            # Find parent: pop stack until we find a section with lower level
            while stack and stack[-1].level >= block.heading_level:
                stack.pop()

            if stack:
                stack[-1].children.append(new_section)
            else:
                root_sections.append(new_section)

            stack.append(new_section)
        else:
            if not stack:
                # Content before any heading — create implicit root section
                root_section = Section(level=0)
                root_sections.append(root_section)
                stack.append(root_section)
            current_content_parts.append(block.text)

    flush_content()
    return root_sections


def _convert_tables(raw_tables: list[RawTable]) -> list[ExtractedTable]:
    """Convert raw tables to ExtractedTable models."""
    tables: list[ExtractedTable] = []
    for rt in raw_tables:
        rows = []
        for row_data in rt.rows:
            row_dict = {}
            for i, cell in enumerate(row_data):
                header = rt.headers[i] if i < len(rt.headers) else f"col_{i}"
                row_dict[header] = cell
            rows.append(row_dict)

        tables.append(ExtractedTable(
            headers=rt.headers,
            rows=rows,
            page_number=rt.page + 1,  # 1-indexed for users
        ))
    return tables


def _convert_images(raw_images: list) -> list[ExtractedImage]:
    """Convert raw images to ExtractedImage models."""
    return [
        ExtractedImage(
            data=img.data,
            format=img.format,
            page_number=img.page + 1,
            width=img.width,
            height=img.height,
        )
        for img in raw_images
    ]


def _build_pages(
    blocks: list[TextBlock],
    tables: list[RawTable],
    images: list,
) -> list[Page]:
    """Build per-page Page objects."""
    # Group by page
    page_blocks: dict[int, list[TextBlock]] = {}
    for b in blocks:
        page_blocks.setdefault(b.page, []).append(b)

    page_tables: dict[int, list[RawTable]] = {}
    for t in tables:
        page_tables.setdefault(t.page, []).append(t)

    all_pages = set(page_blocks.keys()) | set(page_tables.keys())

    pages: list[Page] = []
    for pn in sorted(all_pages):
        content = "\n".join(b.text for b in page_blocks.get(pn, []))
        p_tables = _convert_tables(page_tables.get(pn, []))
        p_images = [
            ExtractedImage(
                data=img.data,
                format=img.format,
                page_number=pn + 1,
                width=img.width,
                height=img.height,
            )
            for img in images
            if img.page == pn
        ]

        pages.append(Page(
            number=pn + 1,  # 1-indexed
            content=content,
            tables=p_tables,
            images=p_images,
        ))

    return pages


def _generate_markdown(blocks: list[TextBlock], tables: list[RawTable]) -> str:
    """Generate markdown from text blocks and tables."""
    if not blocks and not tables:
        return ""

    # Merge blocks and tables, ordered by page then y-position
    parts: list[str] = []
    table_regions = {(t.page, t.y0, t.y1) for t in tables}

    # Track which blocks fall within table regions (skip them in text output)
    def _in_table_region(block: TextBlock) -> bool:
        for tp, ty0, ty1 in table_regions:
            if block.page == tp and ty0 <= block.y0 <= ty1:
                return True
        return False

    # Process blocks page by page
    current_page = -1
    for block in blocks:
        if _in_table_region(block):
            continue

        # Insert tables that come before this block on this page
        if block.page != current_page:
            # Insert any tables from previous pages
            for table in tables:
                if table.page == current_page:
                    parts.append(_table_to_markdown(table))
            current_page = block.page

        if block.is_heading:
            prefix = "#" * block.heading_level
            parts.append(f"\n{prefix} {block.text}\n")
        else:
            parts.append(block.text)

    # Insert remaining tables
    for table in tables:
        if table.page == current_page or current_page == -1:
            parts.append(_table_to_markdown(table))

    return "\n\n".join(part for part in parts if part.strip())


def _table_to_markdown(table: RawTable) -> str:
    """Convert a RawTable to markdown table syntax."""
    if not table.headers:
        return ""

    lines: list[str] = []

    # Header row
    lines.append("| " + " | ".join(table.headers) + " |")

    # Separator
    lines.append("| " + " | ".join("---" for _ in table.headers) + " |")

    # Data rows
    for row in table.rows:
        cells = []
        for i in range(len(table.headers)):
            cells.append(row[i] if i < len(row) else "")
        lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(lines)


def _generate_plain_text(blocks: list[TextBlock]) -> str:
    """Generate plain text content from blocks."""
    return "\n".join(b.text for b in blocks)


def _build_metadata(raw_meta: dict, content: str) -> Metadata:
    """Build Metadata model from raw metadata dict."""
    word_count = len(content.split()) if content else 0

    return Metadata(
        title=raw_meta.get("title"),
        author=raw_meta.get("author"),
        page_count=raw_meta.get("page_count"),
        word_count=word_count,
    )
