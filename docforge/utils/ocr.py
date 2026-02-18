"""OCR wrapper supporting Tesseract and EasyOCR engines, with image preprocessing."""

from __future__ import annotations

import io
import re

from docforge.extractors.base import TextBlock

# Minimum text length to consider a page as having digital text
SCANNED_PAGE_THRESHOLD = 50

# Lines with fewer than this many alphanumeric chars are noise
_MIN_ALNUM_CHARS = 3


def is_scanned_page(text: str, image_count: int) -> bool:
    """Check if a page is scanned (has images but very little text)."""
    return len(text.strip()) < SCANNED_PAGE_THRESHOLD and image_count > 0


def run_ocr(
    image_bytes: bytes,
    page_num: int = 0,
    engine: str = "tesseract",
    language: str = "eng",
) -> list[TextBlock]:
    """Run OCR on an image and return TextBlocks with position info.

    Applies image preprocessing (grayscale, contrast, denoise)
    before OCR to improve accuracy on photos and scans.
    """
    if engine == "easyocr":
        return _run_easyocr(image_bytes, page_num, language)
    return _run_tesseract(image_bytes, page_num, language)


def _preprocess_image(img):  # type: (PIL.Image.Image) -> PIL.Image.Image
    """Preprocess image to improve OCR accuracy.

    Uses a moderate approach: grayscale, upscale, contrast boost, light
    sharpening. Avoids aggressive binarization which can destroy thin text
    or introduce noise on photos with uneven lighting.
    """
    from PIL import Image, ImageEnhance, ImageFilter

    # 1. Grayscale
    img = img.convert("L")

    # 2. Upscale small images for better character recognition
    w, h = img.size
    if w < 2500:
        scale = 2500 / w
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    # 3. Contrast enhancement — makes text darker, background lighter
    img = ImageEnhance.Contrast(img).enhance(1.8)

    # 4. Sharpening — crisper character edges
    img = ImageEnhance.Sharpness(img).enhance(2.0)

    # 5. Light denoise without destroying text
    img = img.filter(ImageFilter.MedianFilter(size=3))

    return img


def _clean_line(text: str) -> str:
    """Clean OCR artifacts from a line of text."""
    # Remove leading/trailing punctuation-only noise (|, ., -, _)
    text = text.strip()
    text = re.sub(r"^[|._\-:;'\"!,\s]+", "", text)
    text = re.sub(r"[|._\-:;'\"!\s]+$", "", text)
    return text.strip()


def _is_noise_line(text: str) -> bool:
    """Check if a line is likely OCR noise rather than real content."""
    alnum_count = sum(1 for c in text if c.isalnum())
    return alnum_count < _MIN_ALNUM_CHARS


def _run_tesseract(image_bytes: bytes, page_num: int, language: str) -> list[TextBlock]:
    """Run Tesseract OCR with preprocessing."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        raise ImportError(
            "Tesseract OCR requires extra dependencies. Install with: "
            "pip install 'docforge[ocr]'\n"
            "Also install Tesseract itself: brew install tesseract (macOS) "
            "or apt-get install tesseract-ocr (Linux)"
        )

    img = Image.open(io.BytesIO(image_bytes))
    processed = _preprocess_image(img)

    # --oem 3: LSTM neural net engine (best accuracy)
    # --psm 4: assume single column of variable-size text
    #   (better reading order than psm 3 for most documents)
    custom_config = "--oem 3 --psm 4"

    data = pytesseract.image_to_data(
        processed,
        lang=language,
        config=custom_config,
        output_type=pytesseract.Output.DICT,
    )

    blocks: list[TextBlock] = []
    n_items = len(data["text"])

    # Group words into lines by (block_num, par_num, line_num)
    lines: dict[tuple[int, int, int], list[int]] = {}
    for i in range(n_items):
        conf = int(data["conf"][i]) if data["conf"][i] != "-1" else -1
        text = data["text"][i].strip()
        if conf < 40 or not text:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines.setdefault(key, []).append(i)

    for key in sorted(lines.keys()):
        indices = lines[key]
        words = [data["text"][i].strip() for i in indices]
        line_text = " ".join(words)

        # Clean artifacts and skip noise
        line_text = _clean_line(line_text)
        if not line_text or _is_noise_line(line_text):
            continue

        # Compute bounding box for the whole line
        x0 = min(data["left"][i] for i in indices)
        y0 = min(data["top"][i] for i in indices)
        x1 = max(data["left"][i] + data["width"][i] for i in indices)
        y1 = max(data["top"][i] + data["height"][i] for i in indices)

        blocks.append(TextBlock(
            text=line_text,
            page=page_num,
            x0=float(x0),
            y0=float(y0),
            x1=float(x1),
            y1=float(y1),
            source="ocr",
        ))

    # Sort by vertical position for correct reading order
    blocks.sort(key=lambda b: (b.y0, b.x0))

    return blocks


def _run_easyocr(image_bytes: bytes, page_num: int, language: str) -> list[TextBlock]:
    """Run EasyOCR."""
    try:
        import easyocr
    except ImportError:
        raise ImportError(
            "EasyOCR requires extra dependencies. Install with: "
            "pip install 'docforge[easyocr]'"
        )

    # Map common language codes
    lang_map = {"eng": "en", "fra": "fr", "deu": "de", "spa": "es"}
    lang = lang_map.get(language, language)

    reader = easyocr.Reader([lang], verbose=False)
    results = reader.readtext(image_bytes)

    blocks: list[TextBlock] = []
    for bbox, text, conf in results:
        if conf < 0.3 or not text.strip():
            continue

        # bbox is [[x0,y0],[x1,y0],[x1,y1],[x0,y1]]
        xs = [p[0] for p in bbox]
        ys = [p[1] for p in bbox]

        blocks.append(TextBlock(
            text=text.strip(),
            page=page_num,
            x0=float(min(xs)),
            y0=float(min(ys)),
            x1=float(max(xs)),
            y1=float(max(ys)),
            source="ocr",
        ))

    return blocks


# ---------------------------------------------------------------------------
# Hybrid extraction helpers
# ---------------------------------------------------------------------------

# Form-page heuristic thresholds
_HYBRID_MIN_CHARS = 50
_HYBRID_MAX_CHARS = 2000
_SHORT_LINE_MAX_WORDS = 5
_SHORT_LINE_RATIO = 0.4  # at least 40% of lines must be short/label-like


def needs_hybrid_extraction(text: str, image_count: int) -> bool:
    """Detect form-like pages that need both digital text and OCR.

    A page is a hybrid candidate when it has a moderate amount of digital text
    (enough that ``is_scanned_page`` would call it digital) **and** embedded
    images, **and** many short label-like lines — the hallmark of a printed
    form whose handwritten values live only in the page image.
    """
    stripped = text.strip()
    char_count = len(stripped)

    if image_count == 0:
        return False
    if char_count < _HYBRID_MIN_CHARS or char_count > _HYBRID_MAX_CHARS:
        return False

    lines = [ln.strip() for ln in stripped.splitlines() if ln.strip()]
    if not lines:
        return False

    short_lines = sum(1 for ln in lines if len(ln.split()) <= _SHORT_LINE_MAX_WORDS)
    return short_lines / len(lines) >= _SHORT_LINE_RATIO


def normalize_ocr_coords(
    blocks: list[TextBlock],
    page_width_pts: float,
    page_height_pts: float,
    dpi: int = 300,
) -> list[TextBlock]:
    """Convert OCR pixel coordinates to PDF points so overlap detection works.

    Tesseract/EasyOCR return coordinates in pixels at the rendered DPI.
    PDF coordinates are in points (1 pt = 1/72 inch).
    """
    if not blocks:
        return blocks

    # rendered image size in pixels
    img_w = page_width_pts * dpi / 72.0
    img_h = page_height_pts * dpi / 72.0

    scale_x = page_width_pts / img_w if img_w else 1.0
    scale_y = page_height_pts / img_h if img_h else 1.0

    for b in blocks:
        b.x0 *= scale_x
        b.y0 *= scale_y
        b.x1 *= scale_x
        b.y1 *= scale_y

    return blocks


def _overlap_ratio(a: TextBlock, b: TextBlock) -> float:
    """Return fraction of *a*'s area covered by intersection with *b*."""
    ix0 = max(a.x0, b.x0)
    iy0 = max(a.y0, b.y0)
    ix1 = min(a.x1, b.x1)
    iy1 = min(a.y1, b.y1)

    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0

    inter = (ix1 - ix0) * (iy1 - iy0)
    area_a = (a.x1 - a.x0) * (a.y1 - a.y0)
    if area_a <= 0:
        return 0.0
    return inter / area_a


_OVERLAP_THRESHOLD = 0.40


def merge_hybrid_blocks(
    digital_blocks: list[TextBlock],
    ocr_blocks: list[TextBlock],
) -> list[TextBlock]:
    """Merge digital text blocks with OCR blocks, discarding OCR duplicates.

    For each OCR block, if it overlaps >=40% with *any* digital block it is
    considered a duplicate of a printed label and is discarded.  Otherwise it
    is kept (handwritten content the digital pass missed).

    Returns all digital blocks + non-overlapping OCR blocks, sorted by (y0, x0).
    """
    kept_ocr: list[TextBlock] = []
    for ocr_b in ocr_blocks:
        is_dup = False
        for dig_b in digital_blocks:
            if ocr_b.page != dig_b.page:
                continue
            if _overlap_ratio(ocr_b, dig_b) >= _OVERLAP_THRESHOLD:
                is_dup = True
                break
        if not is_dup:
            kept_ocr.append(ocr_b)

    merged = list(digital_blocks) + kept_ocr
    merged.sort(key=lambda b: (b.page, b.y0, b.x0))
    return merged
