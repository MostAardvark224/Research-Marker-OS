"""Provider-neutral PDF ingestion, retrieval, and prompt context."""

from .builder import build_paper_context, format_paper_context
from .ingestion import clear_paper_context, ensure_document_ingested, ingest_document
from .retrieval import (
    get_active_document,
    get_current_page,
    get_current_selection,
    get_figure_context,
    get_page,
    get_pages,
    search_document,
)

__all__ = [
    "build_paper_context",
    "clear_paper_context",
    "ensure_document_ingested",
    "format_paper_context",
    "get_active_document",
    "get_current_page",
    "get_current_selection",
    "get_figure_context",
    "get_page",
    "get_pages",
    "ingest_document",
    "search_document",
]
