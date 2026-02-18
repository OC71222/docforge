"""Base extractor ABC and raw extraction dataclasses."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TextBlock:
    text: str
    page: int = 0
    x0: float = 0
    y0: float = 0
    x1: float = 0
    y1: float = 0
    font_size: float = 0
    is_bold: bool = False
    is_heading: bool = False
    heading_level: int = 0
    source: str = "digital"


@dataclass
class RawTable:
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    page: int = 0
    x0: float = 0
    y0: float = 0
    x1: float = 0
    y1: float = 0


@dataclass
class RawImage:
    data: bytes = b""
    format: str = "png"
    page: int = 0
    width: int = 0
    height: int = 0


@dataclass
class RawExtraction:
    text_blocks: list[TextBlock] = field(default_factory=list)
    tables: list[RawTable] = field(default_factory=list)
    images: list[RawImage] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    page_count: int = 0


class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, file_path: Path, **options: object) -> RawExtraction:
        """Extract content from a file. Return raw extraction."""
        ...
