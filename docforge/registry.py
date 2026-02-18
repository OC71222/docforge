"""Extractor registry with decorator-based registration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from docforge.detector import DocumentFormat

if TYPE_CHECKING:
    from docforge.extractors.base import BaseExtractor


class UnsupportedFormatError(Exception):
    pass


_registry: dict[DocumentFormat, type[Any]] = {}


def register(format: DocumentFormat):
    """Decorator to register an extractor class for a document format."""

    def decorator(cls: type) -> type:
        _registry[format] = cls
        return cls

    return decorator


def get_extractor(format: DocumentFormat) -> BaseExtractor:
    """Get an extractor instance for the given format."""
    if format not in _registry:
        raise UnsupportedFormatError(f"No extractor registered for format: {format.value}")
    return _registry[format]()
