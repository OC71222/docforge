"""DocForge — Universal document parser for LLMs."""

from docforge.models import ExtractedTable, Metadata, ParseResult, Section
from docforge.parser import parse

__version__ = "0.1.0"
__all__ = ["parse", "ParseResult", "Section", "ExtractedTable", "Metadata"]

# Register extractors on import
import docforge.extractors  # noqa: F401, E402
