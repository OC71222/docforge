# DocForge

**Turn any document into clean, structured text that LLMs can actually use.**

If you've ever tried feeding a PDF, a scanned form, or an email into an LLM, you know the pain. Raw text extraction gives you garbled layouts, lost headings, tables turned into nonsense, and scanned pages that come back completely empty. You end up spending more time cleaning the input than getting useful output from the model.

DocForge fixes that. One function call, any document, and you get back clean markdown with proper headings, structured tables, metadata, and per-page breakdowns -- ready to drop straight into a prompt.

## Why This Matters for LLMs

LLMs are only as good as the context you give them. When you're building RAG pipelines, document Q&A systems, or any kind of automated analysis, the quality of your document parsing directly determines the quality of your results. Bad parsing means bad answers.

The problem is that real-world documents are messy. A single PDF might have digital text on some pages, scanned images on others, and forms where printed labels sit next to handwritten values. Most parsers handle one of these cases well and completely fail on the rest.

DocForge handles all of them:

- **Digital PDFs** -- extracts text with correct reading order, even across multi-column layouts
- **Scanned documents** -- automatically detects scanned pages and runs OCR with image preprocessing to maximize accuracy
- **Form pages** -- hybrid mode runs both digital extraction and OCR, then merges the results so you get both the printed labels and the handwritten values without duplicates
- **Word docs, HTML, emails** -- same clean output regardless of the source format
- **Tables** -- detected and extracted as structured data, not flattened into unreadable text

The output is markdown that preserves document structure. Headings stay as headings. Tables stay as tables. Sections nest properly. This means your LLM can actually understand what it's reading instead of trying to make sense of a wall of unformatted text.

## Install

```bash
pip install docforge
```

For scanned document support (OCR):

```bash
pip install 'docforge[ocr]'
brew install tesseract        # macOS
# apt-get install tesseract-ocr  # Linux
```

For everything:

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

It works the same way regardless of file type:

```python
result = docforge.parse("document.docx")
result = docforge.parse("page.html")
result = docforge.parse("message.eml")
result = docforge.parse("scan.png")
```

### Scanned and Hybrid Documents

```python
# Scanned pages are detected automatically -- OCR runs when needed
result = docforge.parse("scanned_form.pdf")

# Hybrid mode for forms with printed labels + handwritten values
result = docforge.parse("intake_form.pdf", hybrid=True)

# Use EasyOCR instead of Tesseract
result = docforge.parse("scan.pdf", ocr_engine="easyocr")
```

### Feeding Results to an LLM

```python
import docforge

result = docforge.parse("quarterly_report.pdf")

# The markdown output is ready to use as LLM context
prompt = f"""Based on the following document, summarize the key findings:

{result.markdown}
"""

# Or work with structured data directly
for table in result.tables:
    print(table.headers)  # ['Quarter', 'Revenue', 'Expenses']
    print(table.rows)     # [{'Quarter': 'Q1', 'Revenue': '$100k', ...}]

# Per-page analysis
for page in result.pages:
    print(f"Page {page.number}: {len(page.content)} chars")
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

## Supported Formats

| Format | What it does |
|--------|-------------|
| PDF (digital) | Extracts text with position, font size, bold flags. Detects headings, columns, tables. |
| PDF (scanned) | Renders pages at 300 DPI, preprocesses images, runs OCR. Automatic -- no flag needed. |
| PDF (hybrid forms) | Runs both digital extraction and OCR, merges results by spatial overlap. Use `--hybrid`. |
| Images (PNG, JPG, TIFF, BMP) | Runs OCR with preprocessing (grayscale, upscale, contrast, sharpen, denoise). |
| Word (.docx) | Extracts paragraphs, heading styles, tables, and document properties. |
| HTML | Strips boilerplate (nav, ads, scripts), walks the DOM for headings, paragraphs, and tables. |
| Email (.eml) | Parses headers (from, to, subject, date) and extracts plain text or HTML body. |
| Email (.msg) | Same as .eml, using the extract-msg library. |

## How It Works

DocForge runs a three-stage pipeline:

```
Input (file path, bytes, or URL)
    |
    v
[1] Detect format -- reads magic bytes, checks extension, sniffs content
    |
    v
[2] Extract -- routes to the right extractor, pulls out text blocks with positions
    |
    v
[3] Structure -- builds section tree, generates markdown, extracts tables
    |
    v
Output (ParseResult with markdown, sections, tables, metadata, pages)
```

Each format has its own extractor class that registers itself on import. Adding support for a new format means writing one class and decorating it -- no changes to the core pipeline.

### What Makes the PDF Extractor Different

Most PDF parsers do one thing: dump all the text. DocForge does more:

1. **Reading order** -- detects multi-column layouts by finding gaps in x-coordinates, then reads left column before right column instead of interleaving lines
2. **Heading detection** -- compares each text block's font size against the median. Larger or bolder text gets marked as a heading with the appropriate level
3. **Scanned page detection** -- if a page has images but fewer than 50 characters of digital text, it's treated as a scan and routed through OCR
4. **Hybrid form extraction** -- when a page has some digital text (printed labels) but also images (handwritten fields), hybrid mode runs both extraction methods and uses spatial overlap to merge without duplicating the printed text
5. **Table detection** -- finds horizontal and vertical lines in the PDF's drawing commands to identify table grids, then maps text into cells

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

## Dependencies

**Core** (always installed):
- PyMuPDF -- PDF parsing
- Pydantic v2 -- output models and validation
- Click -- CLI framework
- BeautifulSoup4 -- HTML parsing

**Optional**:
- `docforge[ocr]` -- pytesseract, Pillow (requires system Tesseract install)
- `docforge[easyocr]` -- EasyOCR (no system install needed, uses PyTorch)
- `docforge[docx]` -- python-docx
- `docforge[email]` -- extract-msg (for .msg files; .eml works out of the box)
- `docforge[all]` -- everything above

## Development

```bash
pip install -e '.[dev]'
pytest tests/ -v
```

## License

MIT
