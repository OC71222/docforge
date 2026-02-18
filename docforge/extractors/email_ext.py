"""Email extractor for .eml and .msg files."""

from __future__ import annotations

import email
import email.policy
from pathlib import Path

from docforge.detector import DocumentFormat
from docforge.extractors.base import BaseExtractor, RawExtraction, TextBlock
from docforge.registry import register


@register(DocumentFormat.EMAIL_EML)
class EmlExtractor(BaseExtractor):
    def extract(self, file_path: Path, **options: object) -> RawExtraction:
        raw = file_path.read_bytes()
        msg = email.message_from_bytes(raw, policy=email.policy.default)

        # Extract headers
        subject = msg.get("Subject", "")
        from_addr = msg.get("From", "")
        to_addr = msg.get("To", "")
        date = msg.get("Date", "")

        # Build header block
        blocks: list[TextBlock] = []
        y = 0.0

        if subject:
            blocks.append(TextBlock(
                text=subject,
                page=0, x0=0, y0=y, x1=500, y1=y + 16,
                font_size=16, is_bold=True, is_heading=True, heading_level=1,
            ))
            y += 20

        header_lines = []
        if from_addr:
            header_lines.append(f"From: {from_addr}")
        if to_addr:
            header_lines.append(f"To: {to_addr}")
        if date:
            header_lines.append(f"Date: {date}")

        if header_lines:
            blocks.append(TextBlock(
                text="\n".join(header_lines),
                page=0, x0=0, y0=y, x1=500, y1=y + len(header_lines) * 12,
                font_size=11,
            ))
            y += len(header_lines) * 12 + 8

        # Extract body
        body = self._get_body(msg)
        if body:
            for line in body.strip().splitlines():
                line = line.strip()
                if not line:
                    y += 6
                    continue
                blocks.append(TextBlock(
                    text=line,
                    page=0, x0=0, y0=y, x1=500, y1=y + 12,
                    font_size=11,
                ))
                y += 14

        metadata = {
            "title": subject or None,
            "author": from_addr or None,
            "to": to_addr or None,
            "created_date": date or None,
            "page_count": 1,
        }

        return RawExtraction(
            text_blocks=blocks,
            tables=[],
            images=[],
            metadata=metadata,
            page_count=1,
        )

    def _get_body(self, msg: email.message.Message) -> str:
        """Extract the plain text body from an email message."""
        body = msg.get_body(preferencelist=("plain", "html"))
        if body is None:
            return ""

        content = body.get_content()
        if not isinstance(content, str):
            return ""

        # If HTML, do a basic strip of tags
        content_type = body.get_content_type()
        if content_type == "text/html":
            return self._strip_html(content)

        return content

    def _strip_html(self, html: str) -> str:
        """Basic HTML tag stripping for email bodies."""
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")
            for tag in soup.find_all(["script", "style"]):
                tag.decompose()
            return soup.get_text(separator="\n", strip=True)
        except ImportError:
            # Fallback: crude regex strip
            import re

            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text)
            return text.strip()


@register(DocumentFormat.EMAIL_MSG)
class MsgExtractor(BaseExtractor):
    def extract(self, file_path: Path, **options: object) -> RawExtraction:
        try:
            import extract_msg
        except ImportError:
            raise ImportError(
                "MSG email support requires extract-msg. Install with: "
                "pip install 'docforge[email]'"
            )

        msg = extract_msg.Message(str(file_path))
        try:
            subject = msg.subject or ""
            sender = msg.sender or ""
            to = msg.to or ""
            date = str(msg.date) if msg.date else ""
            body = msg.body or ""

            blocks: list[TextBlock] = []
            y = 0.0

            if subject:
                blocks.append(TextBlock(
                    text=subject,
                    page=0, x0=0, y0=y, x1=500, y1=y + 16,
                    font_size=16, is_bold=True, is_heading=True, heading_level=1,
                ))
                y += 20

            header_lines = []
            if sender:
                header_lines.append(f"From: {sender}")
            if to:
                header_lines.append(f"To: {to}")
            if date:
                header_lines.append(f"Date: {date}")

            if header_lines:
                blocks.append(TextBlock(
                    text="\n".join(header_lines),
                    page=0, x0=0, y0=y, x1=500, y1=y + len(header_lines) * 12,
                    font_size=11,
                ))
                y += len(header_lines) * 12 + 8

            if body:
                for line in body.strip().splitlines():
                    line = line.strip()
                    if not line:
                        y += 6
                        continue
                    blocks.append(TextBlock(
                        text=line,
                        page=0, x0=0, y0=y, x1=500, y1=y + 12,
                        font_size=11,
                    ))
                    y += 14

            metadata = {
                "title": subject or None,
                "author": sender or None,
                "to": to or None,
                "created_date": date or None,
                "page_count": 1,
            }

            return RawExtraction(
                text_blocks=blocks,
                tables=[],
                images=[],
                metadata=metadata,
                page_count=1,
            )
        finally:
            msg.close()
