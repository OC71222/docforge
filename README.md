# DocForge

A document parser that extracts structured text from PDFs, Word docs, HTML, images, and emails.

Most document formats weren't designed to be read by software. PDFs store text as positioned fragments with no concept of paragraphs or sections. Scanned documents are just images. Forms mix printed labels with handwritten values. When you extract text from these naively, you lose structure -- headings flatten into body text, tables become jumbled lines, and multi-column layouts interleave into nonsense.

This is especially problematic when using documents as context for LLMs. Models produce better results when the input preserves the original structure of the document -- when headings are marked as headings, tables remain tabular, and reading order is correct. DocForge parses documents into clean markdown and structured data so that the text you pass to a model actually reflects what a human would see on the page.

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

For all optional dependencies:

```bash
pip install 'docforge[all]'
```

## Usage

```python
import docforge

result = docforge.parse("report.pdf")

result.markdown       # markdown with headings and tables preserved
result.content        # plain text
result.tables         # list of extracted tables with headers and rows
result.sections       # hierarchical section tree based on heading levels
result.pages          # per-page content breakdown
result.metadata       # title, author, page count, word count
```

The same call works for other formats:

```python
result = docforge.parse("document.docx")
result = docforge.parse("page.html")
result = docforge.parse("message.eml")
result = docforge.parse("scan.png")
```

### Scanned and hybrid documents

Scanned pages are detected automatically. If a PDF page has images but very little digital text, DocForge renders it at 300 DPI and runs OCR.

Some documents sit in a grey area -- printed forms where the labels are digital text but the filled-in values are handwritten. The `hybrid` flag handles this by running both digital extraction and OCR, then merging results using spatial overlap so that printed labels aren't duplicated.

```python
result = docforge.parse("intake_form.pdf", hybrid=True)
```

### Using the output with an LLM

The markdown output is meant to be passed directly as context. It preserves the document's structure in a format that models handle well.

```python
result = docforge.parse("quarterly_report.pdf")

prompt = f"""Summarize the key findings from this document:

{result.markdown}
"""
```

Tables are also available as structured data:

```python
for table in result.tables:
    print(table.headers)   # ['Quarter', 'Revenue', 'Expenses']
    print(table.rows)      # [{'Quarter': 'Q1', 'Revenue': '$100k', ...}]
```

### JSON output

```python
json_str = result.to_json()
data = result.to_dict()
```

## CLI

```bash
docforge parse report.pdf
docforge parse report.pdf --format json
docforge parse report.pdf --output result.md
docforge parse form.pdf --pages 1-5 --hybrid
docforge parse scan.pdf --ocr-engine easyocr
docforge parse report.pdf --extract-images
```

## Supported formats

| Format | Notes |
|--------|-------|
| PDF (digital) | Text extraction with heading detection, column ordering, and table detection from grid lines |
| PDF (scanned) | Automatic OCR with image preprocessing. No flag needed. |
| PDF (hybrid forms) | Digital + OCR merged by spatial overlap. Requires `--hybrid`. |
| Images (PNG, JPG, TIFF, BMP) | OCR with preprocessing (grayscale, upscale, contrast, sharpen, denoise) |
| Word (.docx) | Paragraphs, heading styles, tables, and document properties via python-docx |
| HTML | Strips scripts, nav, and boilerplate. Extracts headings, paragraphs, and tables from the DOM. |
| Email (.eml) | Headers and plain text or HTML body using the standard library |
| Email (.msg) | Same as .eml, requires the extract-msg package |

## How it works

DocForge uses a three-stage pipeline: detect the format, extract raw content with position data, then structure it into sections, markdown, and tables.

```
Input (file path, bytes, or URL)
    |
    v
[1] Detect -- magic bytes, file extension, content sniffing
    |
    v
[2] Extract -- format-specific extractor produces text blocks with bounding boxes
    |
    v
[3] Structure -- builds section tree, generates markdown, normalizes tables
    |
    v
Output (ParseResult)
```

Each format has its own extractor class that registers itself via a decorator. New formats can be added without modifying existing code.

### PDF extraction in detail

The PDF extractor does more than dump text. For each page it:

- Extracts text blocks with position, font size, and bold flags
- Detects multi-column layouts by finding gaps in x-coordinates and reads columns in order
- Identifies headings by comparing font sizes to the page median
- Detects scanned pages (few characters of text plus embedded images) and routes them through OCR
- In hybrid mode, runs both digital and OCR extraction on form-like pages and merges using bounding box overlap
- Finds tables by looking for horizontal and vertical lines in the PDF's drawing commands

## Output schema

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

Core (always installed): PyMuPDF, Pydantic v2, Click, BeautifulSoup4

Optional:
- `docforge[ocr]` -- pytesseract and Pillow (also requires a system Tesseract install)
- `docforge[easyocr]` -- EasyOCR (uses PyTorch, no system install needed)
- `docforge[docx]` -- python-docx
- `docforge[email]` -- extract-msg for .msg files (.eml works without extras)
- `docforge[all]` -- everything above

## Development

```bash
pip install -e '.[dev]'
pytest tests/ -v
```

## License

MIT
