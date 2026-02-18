"""Table detection from PDF pages — rule-based and spatial clustering."""

from __future__ import annotations

import fitz

from docforge.extractors.base import RawTable, TextBlock


def detect_tables_from_pdf_page(page: fitz.Page, page_num: int) -> list[RawTable]:
    """Detect tables from PDF drawing commands (lines forming grids)."""
    drawings = page.get_drawings()
    if not drawings:
        return []

    # Collect horizontal and vertical lines
    h_lines: list[tuple[float, float, float, float]] = []  # y, x_start, x_end, original_y
    v_lines: list[tuple[float, float, float, float]] = []  # x, y_start, y_end, original_x

    for drawing in drawings:
        for item in drawing.get("items", []):
            if item[0] == "l":  # line
                p1, p2 = item[1], item[2]
                x1, y1 = p1.x, p1.y
                x2, y2 = p2.x, p2.y

                if abs(y1 - y2) < 2:  # horizontal line
                    h_lines.append((round(y1), min(x1, x2), max(x1, x2), y1))
                elif abs(x1 - x2) < 2:  # vertical line
                    v_lines.append((round(x1), min(y1, y2), max(y1, y2), x1))
            elif item[0] == "re":  # rectangle
                rect = item[1]
                x0, y0, x1, y1 = rect.x0, rect.y0, rect.x1, rect.y1
                h_lines.append((round(y0), x0, x1, y0))
                h_lines.append((round(y1), x0, x1, y1))
                v_lines.append((round(x0), y0, y1, x0))
                v_lines.append((round(x1), y0, y1, x1))

    if len(h_lines) < 2 or len(v_lines) < 2:
        return []

    # Find grid structure: unique y-values for rows, unique x-values for columns
    h_ys = sorted(set(line[0] for line in h_lines))
    v_xs = sorted(set(line[0] for line in v_lines))

    # Need at least 2 rows and 2 columns to form a table
    if len(h_ys) < 2 or len(v_xs) < 2:
        return []

    # Cluster close y-values and x-values (within tolerance)
    h_ys = _cluster_values(h_ys, tolerance=3)
    v_xs = _cluster_values(v_xs, tolerance=3)

    if len(h_ys) < 2 or len(v_xs) < 2:
        return []

    # Extract text in each cell
    rows_data: list[list[str]] = []
    for i in range(len(h_ys) - 1):
        row: list[str] = []
        for j in range(len(v_xs) - 1):
            cell_rect = fitz.Rect(v_xs[j], h_ys[i], v_xs[j + 1], h_ys[i + 1])
            cell_text = page.get_text("text", clip=cell_rect).strip()
            row.append(cell_text)
        rows_data.append(row)

    if not rows_data:
        return []

    # First row is header
    headers = rows_data[0]
    data_rows = rows_data[1:]

    table = RawTable(
        headers=headers,
        rows=data_rows,
        page=page_num,
        x0=v_xs[0],
        y0=h_ys[0],
        x1=v_xs[-1],
        y1=h_ys[-1],
    )

    return [table]


def detect_tables_from_text_blocks(
    blocks: list[TextBlock], page_num: int
) -> list[RawTable]:
    """Detect tables from spatial alignment of text blocks (borderless tables)."""
    if len(blocks) < 4:
        return []

    # Filter to non-heading blocks on the target page
    page_blocks = [b for b in blocks if b.page == page_num and not b.is_heading]
    if len(page_blocks) < 4:
        return []

    # Cluster x0 values to find columns
    x_values = sorted(set(round(b.x0) for b in page_blocks))
    x_clusters = _cluster_values(x_values, tolerance=5)

    if len(x_clusters) < 2:
        return []

    # Cluster y0 values to find rows
    y_values = sorted(set(round(b.y0) for b in page_blocks))
    y_clusters = _cluster_values(y_values, tolerance=5)

    if len(y_clusters) < 2:
        return []

    # Build grid: map blocks to (row, col)
    grid: dict[tuple[int, int], str] = {}
    for block in page_blocks:
        col = _nearest_cluster(round(block.x0), x_clusters)
        row = _nearest_cluster(round(block.y0), y_clusters)
        if col is not None and row is not None:
            grid[(row, col)] = block.text

    # Check if grid is reasonably full (>50% of cells have content)
    total_cells = len(y_clusters) * len(x_clusters)
    if len(grid) < total_cells * 0.5:
        return []

    # Build table
    rows_data: list[list[str]] = []
    for ri, y in enumerate(y_clusters):
        row: list[str] = []
        for ci, x in enumerate(x_clusters):
            row.append(grid.get((ri, ci), ""))
        rows_data.append(row)

    if not rows_data:
        return []

    headers = rows_data[0]
    data_rows = rows_data[1:]

    return [RawTable(headers=headers, rows=data_rows, page=page_num)]


def _cluster_values(values: list[float], tolerance: float = 3) -> list[float]:
    """Cluster nearby values, returning cluster centers."""
    if not values:
        return []

    clusters: list[list[float]] = [[values[0]]]
    for v in values[1:]:
        if v - clusters[-1][-1] <= tolerance:
            clusters[-1].append(v)
        else:
            clusters.append([v])

    return [sum(c) / len(c) for c in clusters]


def _nearest_cluster(value: float, clusters: list[float]) -> int | None:
    """Find the index of the nearest cluster center."""
    if not clusters:
        return None

    min_dist = float("inf")
    best_idx = 0
    for i, c in enumerate(clusters):
        dist = abs(value - c)
        if dist < min_dist:
            min_dist = dist
            best_idx = i

    return best_idx
