"""Pydantic v2 models for DocForge output."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class Metadata(BaseModel):
    title: str | None = None
    author: str | None = None
    created_date: datetime | None = None
    modified_date: datetime | None = None
    page_count: int | None = None
    word_count: int | None = None
    language: str | None = None


class Section(BaseModel):
    heading: str | None = None
    level: int = 0
    content: str = ""
    children: list[Section] = []


class ExtractedTable(BaseModel):
    headers: list[str] = []
    rows: list[dict] = []
    page_number: int | None = None
    caption: str | None = None


class ExtractedImage(BaseModel):
    data: bytes
    format: str
    page_number: int | None = None
    caption: str | None = None
    width: int | None = None
    height: int | None = None


class Page(BaseModel):
    number: int
    content: str
    tables: list[ExtractedTable] = []
    images: list[ExtractedImage] = []


class ParseResult(BaseModel):
    content: str = ""
    markdown: str = ""
    sections: list[Section] = []
    tables: list[ExtractedTable] = []
    metadata: Metadata = Metadata()
    pages: list[Page] = []
    images: list[ExtractedImage] = []
    source_format: str = ""
    parse_time_seconds: float = 0.0

    def to_json(self) -> str:
        return self.model_dump_json(indent=2, exclude={"images": {"__all__": {"data"}}})

    def to_dict(self) -> dict:
        return self.model_dump(exclude={"images": {"__all__": {"data"}}})
