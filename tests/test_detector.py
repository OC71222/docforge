"""Tests for document format detection."""

from __future__ import annotations

from pathlib import Path

from docforge.detector import DocumentFormat, detect


def test_detect_pdf(tmp_path: Path) -> None:
    f = tmp_path / "test.pdf"
    f.write_bytes(b"%PDF-1.4 some content")
    assert detect(f) == DocumentFormat.PDF


def test_detect_png(tmp_path: Path) -> None:
    f = tmp_path / "test.png"
    f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    assert detect(f) == DocumentFormat.IMAGE


def test_detect_jpeg(tmp_path: Path) -> None:
    f = tmp_path / "test.jpg"
    f.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
    assert detect(f) == DocumentFormat.IMAGE


def test_detect_html_by_content(tmp_path: Path) -> None:
    f = tmp_path / "test.txt"
    f.write_text("<!DOCTYPE html><html><body>Hello</body></html>")
    assert detect(f) == DocumentFormat.HTML


def test_detect_html_by_extension(tmp_path: Path) -> None:
    f = tmp_path / "page.html"
    f.write_text("some content")
    assert detect(f) == DocumentFormat.HTML


def test_detect_eml_by_extension(tmp_path: Path) -> None:
    f = tmp_path / "message.eml"
    f.write_text("From: test@example.com\nSubject: Test\n\nBody")
    assert detect(f) == DocumentFormat.EMAIL_EML


def test_detect_unknown(tmp_path: Path) -> None:
    f = tmp_path / "mystery.xyz"
    f.write_bytes(b"\x00\x01\x02\x03\x04\x05\x06\x07")
    assert detect(f) == DocumentFormat.UNKNOWN


def test_detect_nonexistent_file(tmp_path: Path) -> None:
    f = tmp_path / "nonexistent.pdf"
    assert detect(f) == DocumentFormat.UNKNOWN
