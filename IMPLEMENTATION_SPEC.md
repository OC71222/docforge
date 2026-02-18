# DocForge — Implementation Specification

This document is the technical blueprint for building DocForge. It contains everything needed to implement the library: architecture, file structure, dependencies, detailed module specs, and design decisions. A coding agent (like Claude Code) should be able to read this file and build the entire project from it.

---

## Architecture

DocForge uses a 3-stage pipeline:

```
Input (file path, bytes, or URL)
        │
        ▼
[1. Format Detector]  ── Identifies format via magic bytes + MIME + extension
        │
        ▼
[2. Extractor]        ── Format-specific extraction (one extractor per format)
        │
        ▼
[3. Structurer]       ── Normalizes raw extraction into ParseResult
        │
        ▼
    ParseResult       ── Unified output (markdown, JSON, sections, tables)
```

Each extractor is independent and registered in a registry. The dispatcher routes files to the correct extractor based on detected format. New formats = new extractor class, no changes to core.

---

## Project Structure

```
docforge/
├── docforge/
│   ├── __init__.py              # Public API: parse(), ParseResult, version
│   ├── parser.py                # Main parse() orchestration logic
│   ├── detector.py              # Format detection (magic bytes + MIME + extension)
│   ├── models.py                # Pydantic models: ParseResult, Section, Table, etc.
│   ├── structurer.py            # Post-extraction structuring and markdown generation
│   ├── registry.py              # Extractor registry and dispatch
│   ├── extractors/
│   │   ├── __init__.py
│   │   ├── base.py              # Abstract BaseExtractor
│   │   ├── pdf.py               # PDF extractor (digital + OCR fallback)
│   │   ├── image.py             # Image/OCR extractor
│   │   ├── docx_ext.py          # Word document extractor
│   │   ├── html_ext.py          # HTML extractor
│   │   └── email_ext.py         # Email (.eml/.msg) extractor
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── ocr.py               # OCR wrapper (Tesseract + EasyOCR)
│   │   ├── table_detect.py      # Table detection from PDF + images
│   │   ├── markdown.py          # Markdown rendering utilities
│   │   └── download.py          # URL fetching utility
│   └── cli.py                   # Click-based CLI
├── tests/
│   ├── conftest.py              # Shared fixtures, test PDF/doc generators
│   ├── test_detector.py
│   ├── test_pdf.py
│   ├── test_image.py
│   ├── test_docx.py
│   ├── test_html.py
│   ├── test_email.py
│   ├── test_structurer.py
│   ├── test_cli.py
│   └── fixtures/                # Test documents (small, committed to repo)
│       ├── simple.pdf
│       ├── tables.pdf
│       ├── scanned.pdf
│       ├── multicolumn.pdf
│       ├── sample.docx
│       ├── sample.html
│       └── sample.eml
├── benchmarks/
│   ├── run_benchmark.py         # Accuracy + speed benchmarking script
│   └── ground_truth/            # Expected outputs for benchmark docs
├── docs/
│   ├── quickstart.md
│   └── extending.md             # How to write custom extractors
├── pyproject.toml
├── README.md
├── CONTRIBUTING.md
├── LICENSE                      # MIT
└── .github/
    └── workflows/
        └── ci.yml               # GitHub Actions: lint + test on push/PR
```

---

## Dependencies

### pyproject.toml dependency groups

```toml
[project]
name = "docforge"
version = "0.1.0"
description = "Universal document parser for LLMs"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.10"
dependencies = [
    "pymupdf>=1.24.0",
    "pydantic>=2.0.0",
    "click>=8.0.0",
    "beautifulsoup4>=4.12.0",
    "readability-lxml>=0.8.0",
]

[project.optional-dependencies]
ocr = ["pytesseract>=0.3.10", "Pillow>=10.0.0"]
easyocr = ["easyocr>=1.7.0"]
docx = ["python-docx>=1.0.0"]
email = ["extract-msg>=0.48.0"]
tables = ["img2table>=1.2.0"]
all = ["docforge[ocr,easyocr,docx,email,tables]"]
dev = ["pytest>=8.0.0", "pytest-benchmark>=4.0.0", "ruff>=0.4.0", "mypy>=1.10.0"]

[project.scripts]
docforge = "docforge.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.mypy]
python_version = "3.10"
strict = true
```

---

## Module Specifications

### `docforge/__init__.py`

Exposes the public API. Keep this minimal.

```python
from docforge.parser import parse
from docforge.models import ParseResult, Section, ExtractedTable, Metadata

__version__ = "0.1.0"
__all__ = ["parse", "ParseResult", "Section", "ExtractedTable", "Metadata"]
```

---

### `docforge/parser.py`

The main orchestration module. This is where `parse()` lives.

```python
def parse(
    source: str | bytes | Path,
    *,
    filename: str | None = None,        # Required if source is bytes
    ocr_engine: str = "tesseract",       # "tesseract" | "easyocr"
    extract_images: bool = False,
    pages: list[int] | None = None,      # None = all pages
    output_format: str = "both",         # "markdown" | "json" | "both"
) -> ParseResult:
```

**Logic:**
1. If `source` is a string starting with `http://` or `https://`, download to temp file using `utils/download.py`
2. If `source` is `bytes`, write to temp file (use `filename` for extension hint)
3. If `source` is a string/Path, use directly
4. Call `detector.detect(file_path)` to get format
5. Get extractor from `registry.get_extractor(format)`
6. Call `extractor.extract(file_path, **options)` to get raw extraction
7. Call `structurer.structure(raw_result)` to build final `ParseResult`
8. Record `parse_time_seconds`
9. Return `ParseResult`

---

### `docforge/detector.py`

Detects document format from a file.

```python
class DocumentFormat(str, Enum):
    PDF = "pdf"
    IMAGE = "image"
    DOCX = "docx"
    HTML = "html"
    EMAIL_EML = "eml"
    EMAIL_MSG = "msg"
    UNKNOWN = "unknown"

def detect(file_path: Path) -> DocumentFormat:
```

**Detection strategy (in order):**
1. Read first 8 bytes for magic bytes:
   - `%PDF` → PDF
   - `PK\x03\x04` → check for `word/document.xml` inside zip → DOCX (else unknown)
   - `\x89PNG`, `\xFF\xD8\xFF` (JPEG), `II\x2A\x00` or `MM\x00\x2A` (TIFF) → IMAGE
   - `\xD0\xCF\x11\xE0` → check if .msg extension → EMAIL_MSG
2. If magic bytes inconclusive, check extension: `.html`/`.htm` → HTML, `.eml` → EMAIL_EML
3. Try reading as UTF-8 text and check for `<html` or `<!doctype` → HTML
4. Try reading first line for email headers (`From:`, `Subject:`, `MIME-Version:`) → EMAIL_EML
5. Return UNKNOWN if nothing matches

---

### `docforge/registry.py`

Simple extractor registry with decorator-based registration.

```python
_registry: dict[DocumentFormat, type[BaseExtractor]] = {}

def register(format: DocumentFormat):
    """Decorator to register an extractor for a format."""
    def decorator(cls):
        _registry[format] = cls
        return cls
    return decorator

def get_extractor(format: DocumentFormat) -> BaseExtractor:
    """Get an extractor instance for the given format."""
    if format not in _registry:
        raise UnsupportedFormatError(f"No extractor for {format}")
    return _registry[format]()
```

---

### `docforge/extractors/base.py`

Abstract base class all extractors implement.

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class RawExtraction:
    """Intermediate result from an extractor before structuring."""
    text_blocks: list[TextBlock]        # Ordered text with position info
    tables: list[RawTable]              # Detected tables
    images: list[RawImage]              # Extracted images
    metadata: dict                      # Format-specific metadata
    page_count: int = 0

@dataclass
class TextBlock:
    text: str
    page: int = 0
    x0: float = 0          # Bounding box left
    y0: float = 0          # Bounding box top
    x1: float = 0          # Bounding box right
    y1: float = 0          # Bounding box bottom
    font_size: float = 0
    is_bold: bool = False
    is_heading: bool = False
    heading_level: int = 0  # 0 = not a heading

class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, file_path: Path, **options) -> RawExtraction:
        """Extract content from a file. Return raw extraction."""
        ...
```

---

### `docforge/extractors/pdf.py`

The most important extractor. Handles both digital and scanned PDFs.

**Algorithm:**
1. Open PDF with PyMuPDF (`fitz`)
2. For each page:
   a. Extract text blocks with `page.get_text("dict")` — this gives blocks with position, font info
   b. Check if page is scanned: if total extracted text < 50 chars and page has images, mark as scanned
   c. For scanned pages: render to image at 300 DPI, run OCR via `utils/ocr.py`
   d. For digital pages: process text blocks directly
3. Detect reading order:
   a. Sort blocks by y-coordinate (top to bottom)
   b. Group blocks with similar y-coordinates into lines
   c. Within each line, sort by x-coordinate (left to right)
   d. Detect columns: if there are consistent vertical gaps, treat as multi-column
4. Detect headings: blocks with font_size > median_font_size * 1.2 and/or bold → mark as heading
5. Extract tables via `utils/table_detect.py`
6. Extract metadata: `doc.metadata` gives title, author, dates
7. Optionally extract embedded images: `page.get_images()` + `doc.extract_image(xref)`
8. Return `RawExtraction`

**Key PyMuPDF patterns:**
```python
import fitz

doc = fitz.open(file_path)
for page_num, page in enumerate(doc):
    # Text with position info
    text_dict = page.get_text("dict")
    for block in text_dict["blocks"]:
        if block["type"] == 0:  # text block
            for line in block["lines"]:
                for span in line["spans"]:
                    # span has: text, bbox, font, size, flags (bold etc.)
                    pass

    # Check if scanned (low text, has images)
    text = page.get_text()
    images = page.get_images()

    # Render to image for OCR
    pix = page.get_pixmap(dpi=300)
    img_bytes = pix.tobytes("png")

    # Table lines (for rule-based table detection)
    drawings = page.get_drawings()
```

---

### `docforge/extractors/image.py`

For standalone images (not PDFs).

**Algorithm:**
1. Load image with Pillow
2. Detect if document or photo: aspect ratio close to letter/A4 + text density from quick OCR pass
3. Run full OCR via `utils/ocr.py`
4. Apply same table detection pipeline as scanned PDFs
5. Return `RawExtraction` with single page

---

### `docforge/extractors/docx_ext.py`

Word document extraction using `python-docx`.

**Algorithm:**
1. Open with `python-docx`
2. Iterate paragraphs: detect heading style → `heading_level`, collect text
3. Iterate tables: extract rows/cells preserving merge info
4. Extract metadata from core properties
5. Return `RawExtraction`

**Note:** Import python-docx conditionally — raise helpful error if not installed:
```python
try:
    from docx import Document
except ImportError:
    raise ImportError("Install docx support: pip install docforge[docx]")
```

---

### `docforge/extractors/html_ext.py`

HTML content extraction.

**Algorithm:**
1. Read HTML file
2. Run through `readability-lxml` to strip boilerplate (nav, ads, sidebars)
3. Parse cleaned HTML with BeautifulSoup
4. Walk the DOM tree:
   - `<h1>`-`<h6>` → headings with level
   - `<table>` → extract as table
   - `<p>`, `<li>`, `<div>` → text blocks
   - `<img>` → images (just reference, not downloaded)
5. Extract `<title>`, `<meta>` tags for metadata
6. Return `RawExtraction`

---

### `docforge/extractors/email_ext.py`

Email parsing.

**Algorithm for .eml:**
1. Parse with `email.message_from_file()` (stdlib)
2. Extract headers: From, To, Subject, Date → metadata
3. Walk MIME parts: find `text/plain` and `text/html` body parts
4. If HTML body, run through HTML extractor for structure
5. Extract attachments: filename, content-type, bytes
6. Optionally parse attachments recursively with `parse()`

**Algorithm for .msg:**
1. Parse with `extract-msg` library (conditional import)
2. Same extraction pattern as .eml

---

### `docforge/utils/ocr.py`

OCR wrapper that supports multiple engines.

```python
def run_ocr(
    image: bytes | Image.Image,
    engine: str = "tesseract",
    language: str = "eng",
) -> list[TextBlock]:
```

**Tesseract path:**
1. Use `pytesseract.image_to_data(image, output_type=Output.DICT)` for bounding boxes
2. Filter confidence > 30
3. Group words into lines by y-coordinate proximity
4. Return `TextBlock` list with positions

**EasyOCR path:**
1. Use `reader.readtext(image)` for bounding boxes + text
2. Convert to `TextBlock` list

---

### `docforge/utils/table_detect.py`

Table detection from both digital PDFs and images.

```python
def detect_tables_from_pdf_page(page: fitz.Page) -> list[RawTable]:
    """Detect tables from PDF drawing commands (lines/rects)."""

def detect_tables_from_text_blocks(blocks: list[TextBlock]) -> list[RawTable]:
    """Detect tables from spatial alignment of text blocks."""

def detect_tables_from_image(image: bytes) -> list[RawTable]:
    """Detect tables from document image using img2table."""
```

**Rule-based detection (digital PDFs):**
1. Get all drawings from `page.get_drawings()`
2. Find horizontal and vertical lines
3. Find intersections → grid cells
4. Map text blocks to cells by bounding box overlap
5. Build table structure

**Spatial clustering (borderless tables):**
1. Take text blocks that are NOT headings
2. Cluster by x-coordinate to find columns (within tolerance of ~5px)
3. Cluster by y-coordinate to find rows
4. If ≥2 columns and ≥2 rows with consistent alignment → table
5. Build table structure

---

### `docforge/structurer.py`

Converts `RawExtraction` into final `ParseResult`.

```python
def structure(raw: RawExtraction) -> ParseResult:
```

**Logic:**
1. Build `sections` tree from text blocks: group content under headings by level
2. Build `pages` list: group text blocks and tables by page number
3. Generate `markdown` string:
   - Headings → `#`, `##`, `###`
   - Tables → markdown table syntax
   - Regular text → paragraphs separated by blank lines
   - Images → `![caption](image_N.png)` placeholders
4. Generate `content` (plain text, no formatting)
5. Aggregate all tables and images
6. Build `metadata` from raw metadata dict
7. Return `ParseResult`

---

### `docforge/cli.py`

Click-based CLI.

```python
@click.group()
def main(): ...

@main.command()
@click.argument("source")
@click.option("--format", "-f", type=click.Choice(["markdown", "json"]), default="markdown")
@click.option("--output", "-o", type=click.Path(), default=None, help="Output file path")
@click.option("--output-dir", type=click.Path(), default=None, help="Output directory for batch")
@click.option("--recursive", "-r", is_flag=True, help="Process directories recursively")
@click.option("--ocr-engine", type=click.Choice(["tesseract", "easyocr"]), default="tesseract")
@click.option("--pages", type=str, default=None, help="Page range, e.g. '1-5' or '1,3,5'")
def parse(source, format, output, output_dir, recursive, ocr_engine, pages): ...

@main.command()
@click.argument("directory")
@click.option("--compare", type=str, default=None, help="Compare against another tool")
def benchmark(directory, compare): ...
```

---

## Key Design Decisions

### 1. Hybrid OCR Strategy
For PDFs, always try digital extraction first. Only OCR pages where extracted text is suspiciously short (< 50 chars on a non-blank page). This avoids slow, less-accurate OCR when it's not needed.

### 2. Minimal Default Dependencies
`pip install docforge` only installs PyMuPDF, Pydantic, Click, BeautifulSoup4, and readability-lxml. Everything else is optional extras. This keeps install fast and avoids pulling in heavy ML libraries for users who only need PDF parsing.

### 3. No LLM Dependency
v1 uses only traditional extraction (text parsing, OCR, heuristics). No API keys, no network calls for extraction. This keeps it fast, free, and offline-capable. LLM-enhanced extraction can be added later as an optional mode.

### 4. Pydantic v2 for Output Models
Typed output with `.model_dump()`, `.model_dump_json()`, and automatic validation. Makes it easy for downstream code to work with results.

### 5. Extractor Registry Pattern
New formats are added by creating a new extractor class and decorating it with `@register(DocumentFormat.X)`. No changes to core code needed. This makes community contributions easy.

---

## Performance Targets

| Operation | Target | Constraint |
|-----------|--------|-----------|
| 10-page digital PDF | < 2 seconds | No OCR needed |
| 10-page scanned PDF (Tesseract) | < 8 seconds | OCR is the bottleneck |
| Single image OCR | < 3 seconds | |
| DOCX extraction | < 1 second | Mostly XML parsing |
| HTML extraction | < 500ms | No network fetch |
| Memory | < 500MB | For typical docs under 50 pages |

---

## Error Handling Strategy

- `UnsupportedFormatError` — raised when format can't be detected or no extractor exists
- `ExtractionError` — raised when extraction fails (corrupt file, password-protected, etc.)
- `DependencyError` — raised when optional dependency isn't installed (with install instructions in message)
- Never crash silently. If a page fails, log warning and continue with other pages.
- Always return a `ParseResult` even if partially empty — let the user decide what to do with incomplete results.
