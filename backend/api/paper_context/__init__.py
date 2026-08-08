"""Provider-neutral PDF ingestion, retrieval, and prompt context.

Import-light package init so PyInstaller ``collect_submodules`` can discover
submodules without Django settings in its isolated scanner process.
"""

from __future__ import annotations

from typing import Any

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


def __getattr__(name: str) -> Any:
    if name in {"build_paper_context", "format_paper_context"}:
        from .builder import build_paper_context, format_paper_context

        return {
            "build_paper_context": build_paper_context,
            "format_paper_context": format_paper_context,
        }[name]
    if name in {"clear_paper_context", "ensure_document_ingested", "ingest_document"}:
        from .ingestion import clear_paper_context, ensure_document_ingested, ingest_document

        return {
            "clear_paper_context": clear_paper_context,
            "ensure_document_ingested": ensure_document_ingested,
            "ingest_document": ingest_document,
        }[name]
    if name in {
        "get_active_document",
        "get_current_page",
        "get_current_selection",
        "get_figure_context",
        "get_page",
        "get_pages",
        "search_document",
    }:
        from .retrieval import (
            get_active_document,
            get_current_page,
            get_current_selection,
            get_figure_context,
            get_page,
            get_pages,
            search_document,
        )

        return {
            "get_active_document": get_active_document,
            "get_current_page": get_current_page,
            "get_current_selection": get_current_selection,
            "get_figure_context": get_figure_context,
            "get_page": get_page,
            "get_pages": get_pages,
            "search_document": search_document,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
