# DocForge — Product Requirements Document

## What Is This

DocForge is an open-source Python library that converts messy real-world documents (PDFs, scanned images, Word docs, HTML, emails) into clean structured data ready for LLMs. One function call, any document, clean output.

## The Problem

Developers building LLM apps waste weeks writing brittle glue code to parse documents. PDFs lose table structure. Scanned docs need separate OCR pipelines. Every format needs different libraries. No single tool handles all formats reliably and outputs consistent structured data.

## Target Users

- Solo AI developers building RAG pipelines, chatbots, AI apps
- Small startup teams (2-15 engineers) who don't want to maintain parsing infrastructure
- Open-source contributors looking for a well-architected project to build on

## Core API — This Is What Users See

```python
import docforge

# One-liner — this is the entire API surface for basic usage
result = docforge.parse("invoice.pdf")

# Access output
result.markdown        # Clean markdown string
result.content         # Plain text
result.tables          # List of tables as list[dict]
result.sections        # Structured sections with hierarchy
result.metadata        # Title, author, page count, dates
result.pages           # Per-page content
result.images          # Extracted embedded images
result.source_format   # What format was detected
result.to_json()       # Full JSON export
result.to_dict()       # Dict export

# With options
result = docforge.parse("scan.pdf",
    ocr_engine="easyocr",      # default is "tesseract"
    extract_images=True,        # pull out embedded images
    pages=[1, 2, 3],           # specific pages only
    output_format="markdown",   # "markdown" | "json" | "both"
)

# Parse from bytes/buffer (not just file paths)
result = docforge.parse(file_bytes, filename="doc.pdf")

# Parse from URL
result = docforge.parse("https://example.com/report.pdf")
```

## CLI Interface

```bash
# Parse single file
docforge parse invoice.pdf

# Parse to JSON
docforge parse invoice.pdf --format json --output result.json

# Parse directory recursively
docforge parse ./documents/ --recursive --format markdown --output-dir ./parsed/

# Benchmark against test corpus
docforge benchmark ./test-docs/ --compare unstructured
```

## Supported Input Formats

| Format | Extensions | Priority | Notes |
|--------|-----------|----------|-------|
| PDF (digital) | .pdf | P0 — Must have for launch | Table extraction, multi-column, reading order |
| PDF (scanned) | .pdf | P0 — Must have for launch | Auto-detects scanned pages, falls back to OCR |
| Images | .png .jpg .tiff .bmp | P1 — Fast follow | OCR-based, document image detection |
| Word | .docx | P1 — Fast follow | Preserve heading hierarchy, tables, lists |
| HTML | .html .htm | P1 — Fast follow | Boilerplate removal, clean structure extraction |
| Email | .eml .msg | P2 — Later | Headers, body, nested attachment parsing |

## Output Schema — ParseResult

```python
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class Metadata(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    created_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None
    page_count: Optional[int] = None
    word_count: Optional[int] = None
    language: Optional[str] = None

class Section(BaseModel):
    heading: Optional[str] = None
    level: int = 0                    # 0 = no heading, 1 = h1, 2 = h2, etc.
    content: str = ""
    children: list["Section"] = []

class ExtractedTable(BaseModel):
    headers: list[str] = []
    rows: list[dict] = []             # Each row is {header: value}
    page_number: Optional[int] = None
    caption: Optional[str] = None

class ExtractedImage(BaseModel):
    data: bytes
    format: str                        # "png", "jpg", etc.
    page_number: Optional[int] = None
    caption: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None

class Page(BaseModel):
    number: int
    content: str
    tables: list[ExtractedTable] = []
    images: list[ExtractedImage] = []

class ParseResult(BaseModel):
    content: str                       # Full plain text
    markdown: str                      # Formatted markdown
    sections: list[Section] = []
    tables: list[ExtractedTable] = []
    metadata: Metadata = Metadata()
    pages: list[Page] = []
    images: list[ExtractedImage] = []
    source_format: str = ""
    parse_time_seconds: float = 0.0

    def to_json(self) -> str: ...
    def to_dict(self) -> dict: ...
```

## Competitive Positioning

| Tool | What they do well | Where DocForge wins |
|------|------------------|-------------------|
| Unstructured.io | Broad format support | Higher accuracy on complex tables/layouts, lighter weight |
| LlamaParse | Good PDF parsing | Fully local, no API key needed, not locked to LlamaIndex |
| pdfplumber | Precise PDF text | Multi-format, auto table detection, OCR built-in |
| Marker | Great PDF-to-markdown | Multi-format, JSON output, metadata extraction |
| Docling (IBM) | Good doc understanding | More formats, stronger community focus |

## Success Metrics

| Metric | 6-month target | 12-month target |
|--------|---------------|----------------|
| GitHub stars | 1,000 | 5,000 |
| PyPI monthly downloads | 10,000 | 50,000 |
| Table extraction accuracy | >85% | >92% |
| Avg parse time (10-page PDF) | <3s | <2s |

## Non-Goals for v1

- No hosted API service — library only
- No enterprise features (SSO, audit logs)
- No custom ML model training — use existing models
- No real-time streaming — batch only
- No explicit non-English optimization (should still work, just not tuned)
- No LLM-based extraction (keep it fast and local, no API keys required)
