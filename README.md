# DocForge

Universal document parser for LLMs. One function call, any document, clean structured output.

DocForge takes messy real-world documents -- PDFs, scanned forms, images -- and produces clean markdown, structured sections, extracted tables, and rich metadata. It handles digital text, scanned pages via OCR, and hybrid form pages where printed labels and handwritten values coexist.

## Features

- **Single entry point** -- `docforge.parse()` handles everything
- **PDF extraction** with font-aware heading detection and multi-column reading order
- **OCR fallback** for scanned pages using Tesseract or EasyOCR, with automatic image preprocessing
- **Hybrid mode** for form pages that mix digital text with handwritten fields
- **Table detection** from PDF drawing commands (grid lines)
- **Structured output** -- markdown, hierarchical sections, tables as dicts, per-page breakdown
- **Pluggable architecture** -- add new formats by registering an extractor class

## Install

```bash
pip install docforge
```

For OCR support (scanned documents):

```bash
pip install 'docforge[ocr]'
brew install tesseract        # macOS
# apt-get install tesseract-ocr  # Linux
```

For all optional dependencies:

```bash
pip install 'docforge[all]'
```

## Quick Start

```python
import docforge

result = docforge.parse("report.pdf")

print(result.markdown)       # Clean markdown with headings and tables
print(result.content)        # Plain text, no formatting
print(result.tables)         # Extracted tables as structured data
print(result.metadata)       # Title, author, page count, word count
print(result.sections)       # Hierarchical section tree
print(result.pages)          # Per-page content breakdown
```

### Scanned and Hybrid Documents

```python
# Scanned PDF -- OCR runs automatically when digital text is absent
result = docforge.parse("scanned_form.pdf")

# Hybrid mode -- captures handwritten field values on printed forms
result = docforge.parse("intake_form.pdf", hybrid=True)

# Use EasyOCR instead of Tesseract
result = docforge.parse("scan.pdf", ocr_engine="easyocr")
```

### Page Filtering and Image Extraction

```python
# Parse only specific pages
result = docforge.parse("long_report.pdf", pages=[1, 2, 3])

# Extract embedded images
result = docforge.parse("report.pdf", extract_images=True)
for img in result.images:
    print(img.format, img.width, img.height)
```

### JSON Output

```python
result = docforge.parse("report.pdf")

json_str = result.to_json()   # Full JSON serialization
data = result.to_dict()       # Python dict
```

## CLI

```bash
# Parse to markdown (default)
docforge parse report.pdf

# Parse to JSON
docforge parse report.pdf --format json

# Write output to file
docforge parse report.pdf --output result.md

# Parse specific pages with hybrid mode
docforge parse form.pdf --pages 1-5 --hybrid

# Use EasyOCR engine
docforge parse scan.pdf --ocr-engine easyocr

# Extract images
docforge parse report.pdf --extract-images
```

## Architecture

DocForge uses a three-stage pipeline:

```
Input (file path, bytes, or URL)
    |
    v
[1] Format Detection -- magic bytes, MIME type, file extension
    |
    v
[2] Extraction -- format-specific extractor (registered via plugin system)
    |
    v
[3] Structuring -- normalize raw blocks into ParseResult
    |
    v
Output (ParseResult with markdown, sections, tables, metadata)
```

### Format Detection

The detector reads the first 8 bytes of a file to identify format by magic bytes (`%PDF`, PNG signature, JPEG SOI, etc.), then falls back to file extension and text-based heuristics for HTML and email formats.

### Extraction

Each document format has a dedicated extractor class registered with `@register(DocumentFormat.X)`. Currently implemented:

- **PDF** -- digital text via PyMuPDF, OCR via Tesseract/EasyOCR, table detection via drawing commands

The extractor registry makes it straightforward to add new formats -- write a class that implements `BaseExtractor.extract()`, decorate it with `@register`, and import it. No changes to core code required.

### PDF Extraction Details

For each page, the PDF extractor:

1. Extracts digital text with position, font size, and bold flags from PyMuPDF
2. Checks if the page is scanned (fewer than 50 characters of digital text with embedded images)
3. If scanned: renders the page at 300 DPI and runs OCR with preprocessing (grayscale, upscale, contrast boost, sharpening, denoise)
4. If hybrid mode is enabled and the page looks like a form (50-2000 chars, many short label-like lines): runs both digital extraction and OCR, then merges results using spatial overlap to avoid duplicating printed labels while keeping handwritten values
5. Detects headings by comparing font sizes to the median across all blocks
6. Detects multi-column layouts by finding significant gaps in x-coordinates
7. Extracts tables by finding horizontal and vertical grid lines in PDF drawing commands

### Structuring

The structurer converts raw text blocks into:

- A hierarchical section tree based on heading levels
- Markdown with proper heading markers and table syntax
- Plain text content
- Per-page breakdowns with associated tables and images
- Metadata including computed word count

## Output Schema

```
ParseResult
  content: str              -- full plain text
  markdown: str             -- formatted markdown
  sections: list[Section]   -- hierarchical tree
  tables: list[ExtractedTable]
  pages: list[Page]         -- per-page breakdown
  images: list[ExtractedImage]
  metadata: Metadata
  source_format: str
  parse_time_seconds: float

Section
  heading: str | None
  level: int               -- 0=root, 1=h1, 2=h2, 3=h3
  content: str
  children: list[Section]

ExtractedTable
  headers: list[str]
  rows: list[dict]         -- each row is {header: value}
  page_number: int | None

Metadata
  title, author: str | None
  page_count, word_count: int | None
  created_date, modified_date: datetime | None
```

## Project Structure

```
docforge/
  __init__.py          -- public API (parse, models)
  parser.py            -- main orchestration
  detector.py          -- format detection (magic bytes, extension, heuristics)
  registry.py          -- extractor plugin registry
  structurer.py        -- raw blocks to ParseResult
  models.py            -- Pydantic v2 output models
  cli.py               -- Click CLI
  extractors/
    base.py            -- TextBlock, RawTable, RawImage, BaseExtractor
    pdf.py             -- PDF extractor (digital + OCR + hybrid)
  utils/
    ocr.py             -- Tesseract/EasyOCR wrapper, preprocessing, hybrid merge
    table_detect.py    -- table detection from drawing commands
    download.py        -- URL fetching to temp files
tests/
  test_pdf.py          -- PDF extraction and integration tests
  test_ocr.py          -- OCR and hybrid merge unit tests
  test_structurer.py   -- structuring pipeline tests
  test_detector.py     -- format detection tests
```

## Dependencies

**Core** (always installed):
- PyMuPDF -- PDF parsing
- Pydantic v2 -- output models and validation
- Click -- CLI framework

**Optional**:
- `docforge[ocr]` -- pytesseract, Pillow (requires system Tesseract install)
- `docforge[easyocr]` -- EasyOCR (no system install needed, uses PyTorch)
- `docforge[docx]` -- python-docx (not yet implemented)
- `docforge[html]` -- BeautifulSoup4, readability-lxml (not yet implemented)
- `docforge[email]` -- extract-msg (not yet implemented)
- `docforge[all]` -- everything above

## Development

```bash
pip install -e '.[dev]'
pytest tests/ -v
```

## License

MIT
