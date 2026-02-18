# DocForge — Development TODO

Step-by-step build checklist. Complete each phase before moving to the next. Each task is a single work session or PR.

---

## Phase 0: Project Scaffolding (Week 1)

**Goal:** Repo, packaging, CI, skeleton code. `pip install -e .` works. Tests run (even if empty).

- [ ] Create project directory with structure from IMPLEMENTATION_SPEC.md
- [ ] Write `pyproject.toml` with all dependency groups (core, ocr, easyocr, docx, email, tables, all, dev)
- [ ] Write `docforge/models.py` — all Pydantic models: `ParseResult`, `Section`, `ExtractedTable`, `Metadata`, `Page`, `ExtractedImage`
- [ ] Write `docforge/extractors/base.py` — `BaseExtractor` ABC, `RawExtraction`, `TextBlock`, `RawTable`, `RawImage` dataclasses
- [ ] Write `docforge/detector.py` — format detection with magic bytes + extension fallback
- [ ] Write `docforge/registry.py` — extractor registry with `@register` decorator
- [ ] Write `docforge/parser.py` — main `parse()` function with orchestration (detect → extract → structure)
- [ ] Write `docforge/structurer.py` — stub that converts `RawExtraction` → `ParseResult` (basic version)
- [ ] Write `docforge/__init__.py` — expose `parse`, `ParseResult`, `__version__`
- [ ] Write `docforge/cli.py` — Click CLI skeleton with `parse` and `benchmark` commands
- [ ] Create `tests/conftest.py` with fixtures
- [ ] Write `tests/test_detector.py` — test format detection with small fixture files
- [ ] Set up `ruff` for linting in pyproject.toml
- [ ] Write `.github/workflows/ci.yml` — GitHub Actions: install, lint, test on push/PR
- [ ] Write `README.md` — project name, one-paragraph description, install command, basic usage code block, "Under Development" badge
- [ ] Write `CONTRIBUTING.md` — clone, install dev, run tests, PR process
- [ ] Add `LICENSE` (MIT)
- [ ] Verify: `pip install -e ".[dev]"` works, `pytest` runs, `ruff check .` passes

---

## Phase 1: PDF Extraction — Digital (Weeks 2-3)

**Goal:** `docforge.parse("digital.pdf")` returns accurate text with reading order, headings, and tables.

### Core Text Extraction
- [ ] Write `docforge/extractors/pdf.py` — register for `DocumentFormat.PDF`
- [ ] Implement text extraction using `fitz.open()` + `page.get_text("dict")`
- [ ] Extract per-span info: text, bbox (x0, y0, x1, y1), font_size, bold flag
- [ ] Build `TextBlock` objects from spans, grouped by line

### Reading Order
- [ ] Implement column detection: cluster text blocks by x-coordinate gaps
- [ ] Sort blocks: top-to-bottom within columns, left-to-right across columns
- [ ] Handle single-column, two-column, and three-column layouts

### Heading Detection
- [ ] Calculate median font size across document
- [ ] Mark blocks as headings if font_size > median * 1.2 or bold + larger
- [ ] Assign heading levels: largest = h1, next = h2, etc. (relative to document)

### Table Detection (Rule-Based)
- [ ] Write `docforge/utils/table_detect.py`
- [ ] Implement `detect_tables_from_pdf_page()`: find grid lines from `page.get_drawings()`
- [ ] Find horizontal and vertical line intersections to build cell grid
- [ ] Map text blocks into cells by bounding box overlap
- [ ] Implement `detect_tables_from_text_blocks()`: spatial clustering fallback for borderless tables
- [ ] Output tables as `RawTable` with headers and rows

### Metadata
- [ ] Extract `doc.metadata` (title, author, creation date, page count)
- [ ] Map to `Metadata` model

### Structurer (Full Implementation)
- [ ] Build section tree: group text blocks under headings by level hierarchy
- [ ] Generate markdown: headings with `#`, tables with `|` syntax, paragraphs with blank lines
- [ ] Generate plain text content (no formatting)
- [ ] Build per-page `Page` objects
- [ ] Aggregate tables, compute word count

### Testing
- [ ] Create test fixture: `fixtures/simple.pdf` (basic text, headings)
- [ ] Create test fixture: `fixtures/tables.pdf` (at least 2 tables, one with borders, one without)
- [ ] Create test fixture: `fixtures/multicolumn.pdf` (2-column layout)
- [ ] Write `tests/test_pdf.py`:
  - [ ] Test basic text extraction accuracy
  - [ ] Test heading detection
  - [ ] Test table extraction (correct headers and row count)
  - [ ] Test multi-column reading order
  - [ ] Test metadata extraction
- [ ] Write `tests/test_structurer.py` — test markdown generation, section tree building
- [ ] All tests passing

---

## Phase 2: PDF Extraction — Scanned/OCR (Week 4)

**Goal:** `docforge.parse("scanned.pdf")` auto-detects scanned pages and runs OCR.

### OCR Integration
- [ ] Write `docforge/utils/ocr.py`
- [ ] Implement Tesseract path: `pytesseract.image_to_data()` → `TextBlock` list with bboxes
- [ ] Implement EasyOCR path: `reader.readtext()` → `TextBlock` list
- [ ] Handle engine selection via parameter
- [ ] Add graceful error if Tesseract not installed on system (helpful error message)

### Scanned Page Detection
- [ ] In pdf.py: after digital text extraction, check if text < 50 chars AND page has images
- [ ] If scanned: render page to image at 300 DPI with `page.get_pixmap(dpi=300)`
- [ ] Pass image through OCR pipeline
- [ ] Merge OCR results back into page's text blocks

### Table Detection from Images
- [ ] Implement `detect_tables_from_image()` using img2table (conditional import)
- [ ] Apply to OCR'd pages after text extraction
- [ ] Fall back to spatial clustering if img2table not installed

### Testing
- [ ] Create test fixture: `fixtures/scanned.pdf` (a scanned document image in PDF)
- [ ] Write tests for scanned detection + OCR accuracy
- [ ] Test that digital PDFs do NOT trigger OCR (performance)
- [ ] Test mixed documents (some pages digital, some scanned)

---

## Phase 3: Additional Formats (Weeks 5-7)

**Goal:** Images, DOCX, HTML all work through the same `parse()` interface.

### Image Extractor
- [ ] Write `docforge/extractors/image.py`
- [ ] Load image with Pillow
- [ ] Route through OCR pipeline from utils/ocr.py
- [ ] Apply table detection from image
- [ ] Support PNG, JPG, TIFF, BMP
- [ ] Write `tests/test_image.py`

### DOCX Extractor
- [ ] Write `docforge/extractors/docx_ext.py` (conditional import of python-docx)
- [ ] Extract paragraphs with heading styles → heading level
- [ ] Extract tables preserving structure
- [ ] Extract core properties → metadata
- [ ] Handle lists (bullet and numbered) → text with indicators
- [ ] Write `tests/test_docx.py`

### HTML Extractor
- [ ] Write `docforge/extractors/html_ext.py`
- [ ] Use readability-lxml to strip boilerplate
- [ ] Walk DOM: h1-h6 → headings, table → tables, p/li → text
- [ ] Extract title and meta tags → metadata
- [ ] Write `tests/test_html.py`

### Email Extractor
- [ ] Write `docforge/extractors/email_ext.py`
- [ ] Handle .eml with stdlib email module
- [ ] Handle .msg with extract-msg (conditional import)
- [ ] Extract headers (From, To, Subject, Date) → metadata
- [ ] Extract body (prefer plain text, fall back to HTML → run through HTML extractor)
- [ ] List attachments in metadata
- [ ] Write `tests/test_email.py`

### CLI Polish
- [ ] Implement `parse` command fully: single file, directory, recursive, output options
- [ ] Implement page range parsing (e.g., "1-5" or "1,3,5")
- [ ] Add progress bar for batch processing (click.progressbar)
- [ ] Write `tests/test_cli.py`

---

## Phase 4: Quality, Benchmarks, Docs (Weeks 8-9)

**Goal:** Benchmarked quality, comparison with competitors, polished docs.

### Benchmarking
- [ ] Collect 30+ diverse real-world test documents (invoices, contracts, research papers, manuals, forms)
- [ ] Create ground truth markdown for 10 key documents (manually verified)
- [ ] Write `benchmarks/run_benchmark.py`:
  - [ ] Text accuracy: character-level similarity between output and ground truth
  - [ ] Table F1: precision/recall on table cell values
  - [ ] Parse speed: time per document
- [ ] Run benchmarks against Unstructured.io and LlamaParse on the same corpus
- [ ] Document results in a `BENCHMARKS.md` file

### Edge Cases & Hardening
- [ ] Handle password-protected PDFs (raise clear error)
- [ ] Handle corrupt/truncated files gracefully
- [ ] Handle zero-page PDFs
- [ ] Handle extremely large files (>100 pages) without OOM
- [ ] Handle PDFs with embedded fonts that don't map to Unicode
- [ ] Test with non-English documents (ensure they don't crash, even if quality isn't optimized)

### Documentation
- [ ] Write full `README.md`:
  - [ ] Badges (PyPI version, tests passing, license)
  - [ ] One-paragraph description
  - [ ] Install instructions (core and optional extras)
  - [ ] Quick start code examples
  - [ ] Supported formats table
  - [ ] CLI usage
  - [ ] Benchmark results summary
  - [ ] Contributing link
- [ ] Write `docs/quickstart.md` — extended tutorial with examples
- [ ] Write `docs/extending.md` — how to write a custom extractor
- [ ] Add docstrings to all public functions and classes

### Type Checking
- [ ] Run `mypy --strict` and fix all type errors
- [ ] Add `py.typed` marker file

---

## Phase 5: Ship & Get Traction (Weeks 10-12)

**Goal:** Published on PyPI, visible to the community, first users.

### Publishing
- [ ] Register `docforge` name on PyPI (or alternative if taken)
- [ ] Set up trusted publisher on PyPI via GitHub Actions
- [ ] Write GitHub Actions workflow for auto-publish on tag/release
- [ ] Publish v0.1.0 to PyPI
- [ ] Verify `pip install docforge` works from PyPI

### Launch
- [ ] Write launch blog post: what it does, why it exists, benchmarks vs competitors, future plans
- [ ] Post on Hacker News (Show HN)
- [ ] Post on Reddit: r/LocalLLaMA, r/MachineLearning, r/Python
- [ ] Post on Twitter/X with code examples and benchmark screenshots
- [ ] Share in relevant Discord communities (LangChain, LlamaIndex, etc.)

### Community
- [ ] Set up GitHub issue templates (bug report, feature request)
- [ ] Set up GitHub Discussions for questions
- [ ] Label "good first issue" on 5+ issues for new contributors
- [ ] Respond to every issue and PR within 24 hours for first month

---

## Future / Backlog (Post-Launch)

- [ ] LLM-enhanced extraction mode (optional, uses API for hard cases)
- [ ] Streaming/chunked output for large documents
- [ ] Hosted API service (paid, for users who don't want to self-host)
- [ ] VS Code extension for preview
- [ ] Support for spreadsheets (.xlsx, .csv)
- [ ] Support for PowerPoint (.pptx)
- [ ] Document layout visualization (debug mode that shows detected regions)
- [ ] Fine-tuned table detection model trained on user-submitted corrections
- [ ] Async parse support
- [ ] Batch processing with multiprocessing
