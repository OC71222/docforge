"""Document format detection via magic bytes and extension fallback."""

from __future__ import annotations

import zipfile
from enum import Enum
from pathlib import Path


class DocumentFormat(str, Enum):
    PDF = "pdf"
    IMAGE = "image"
    DOCX = "docx"
    HTML = "html"
    EMAIL_EML = "eml"
    EMAIL_MSG = "msg"
    UNKNOWN = "unknown"


# Magic byte signatures
_MAGIC = {
    b"%PDF": DocumentFormat.PDF,
    b"\x89PNG": DocumentFormat.IMAGE,
    b"\xff\xd8\xff": DocumentFormat.IMAGE,
    b"II\x2a\x00": DocumentFormat.IMAGE,  # TIFF LE
    b"MM\x00\x2a": DocumentFormat.IMAGE,  # TIFF BE
}

_EXT_MAP = {
    ".pdf": DocumentFormat.PDF,
    ".png": DocumentFormat.IMAGE,
    ".jpg": DocumentFormat.IMAGE,
    ".jpeg": DocumentFormat.IMAGE,
    ".tiff": DocumentFormat.IMAGE,
    ".tif": DocumentFormat.IMAGE,
    ".bmp": DocumentFormat.IMAGE,
    ".docx": DocumentFormat.DOCX,
    ".html": DocumentFormat.HTML,
    ".htm": DocumentFormat.HTML,
    ".eml": DocumentFormat.EMAIL_EML,
    ".msg": DocumentFormat.EMAIL_MSG,
}


def detect(file_path: Path) -> DocumentFormat:
    """Detect document format from file contents and extension."""
    file_path = Path(file_path)

    # 1. Magic bytes
    try:
        with open(file_path, "rb") as f:
            header = f.read(8)
    except OSError:
        return DocumentFormat.UNKNOWN

    for magic, fmt in _MAGIC.items():
        if header[: len(magic)] == magic:
            return fmt

    # PK signature — check if DOCX (zip with word/document.xml)
    if header[:4] == b"PK\x03\x04":
        try:
            with zipfile.ZipFile(file_path) as zf:
                if "word/document.xml" in zf.namelist():
                    return DocumentFormat.DOCX
        except zipfile.BadZipFile:
            pass

    # OLE2 compound — check if .msg
    if header[:4] == b"\xd0\xcf\x11\xe0":
        if file_path.suffix.lower() == ".msg":
            return DocumentFormat.EMAIL_MSG

    # 2. Extension fallback
    ext = file_path.suffix.lower()
    if ext in _EXT_MAP:
        return _EXT_MAP[ext]

    # 3. Try reading as text for HTML detection
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            start = f.read(1024).lower().strip()
        if start.startswith("<!doctype") or "<html" in start:
            return DocumentFormat.HTML
        # 4. Email header detection
        first_line = start.split("\n")[0] if start else ""
        if any(first_line.startswith(h) for h in ("from:", "subject:", "mime-version:")):
            return DocumentFormat.EMAIL_EML
    except (UnicodeDecodeError, OSError):
        pass

    return DocumentFormat.UNKNOWN
