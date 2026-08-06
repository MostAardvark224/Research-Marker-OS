from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from api.errors import DocumentNotFound, PageOutOfRange, ResearchMarkerError
from api.paper_context.builder import build_paper_context, format_paper_context
from api.paper_context.retrieval import (
    get_active_context,
    get_active_document,
    get_current_selection,
    get_page,
    get_pages,
    search_document,
)
from api.paper_context.types import ContextLimits
from api.user_preferences import deep_get, load_user_preferences


def _context_limits() -> ContextLimits:
    prefs = load_user_preferences()
    values = deep_get(prefs, "context_limits", default={}) or {}

    def setting(name: str, default: int) -> int:
        try:
            return max(1, int(values.get(name, default)))
        except (TypeError, ValueError):
            return default

    return ContextLimits(
        maximum_explicit_pages=setting("maximum_explicit_pages", 20),
        maximum_retrieved_chunks=setting("maximum_retrieved_chunks", 6),
        maximum_text_characters=setting("maximum_text_characters", 48_000),
        maximum_page_images=setting("maximum_page_images", 4),
        maximum_image_bytes=setting("maximum_image_bytes", 8 * 1024 * 1024),
    )


def _require_active_document_id(document_id: int | None = None) -> int:
    if document_id is not None:
        return int(document_id)
    active = get_active_document()
    if not active:
        raise DocumentNotFound(
            "No paper is active in Research Marker. Open a PDF in the viewer first."
        )
    return int(active["document_id"])


def _image_payload(path: str | None, limits: ContextLimits) -> dict[str, Any] | None:
    if not path:
        return None
    file_path = Path(path)
    try:
        if not file_path.is_file():
            return None
        size = file_path.stat().st_size
        if size <= 0 or size > limits.maximum_image_bytes:
            return None
        data = base64.b64encode(file_path.read_bytes()).decode("ascii")
    except OSError:
        return None
    return {
        "path": str(file_path),
        "mime_type": "image/png",
        "base64": data,
        "byte_size": size,
    }


def active_paper_payload() -> dict[str, Any]:
    state = get_active_context()
    document = get_active_document()
    selection = get_current_selection()
    if not document:
        return {
            "active": False,
            "message": "No paper is open in Research Marker.",
            "state": {
                "document_id": state.document_id,
                "current_page": state.current_page,
                "last_updated": state.last_updated,
            },
        }
    return {
        "active": True,
        "document_id": document["document_id"],
        "document_title": document["document_title"],
        "document_hash": document["document_hash"],
        "page_count": document["page_count"],
        "current_page": state.current_page,
        "has_selection": bool(selection and selection.get("text")),
        "selected_text_page": state.selected_text_page,
        "last_updated": state.last_updated,
    }


def page_payload(
    *,
    page_number: int | None = None,
    document_id: int | None = None,
    include_image: bool = False,
) -> dict[str, Any]:
    limits = _context_limits()
    doc_id = _require_active_document_id(document_id)
    state = get_active_context()
    resolved_page = page_number if page_number is not None else state.current_page
    if resolved_page is None:
        raise PageOutOfRange(
            "No page number was provided and no current page is active.",
            details={"document_id": doc_id},
        )
    page = get_page(
        doc_id,
        int(resolved_page),
        include_image=include_image,
        reason="explicit_page_reference" if page_number is not None else "current_page",
    )
    payload = page.to_dict(expose_local_path=True)
    if include_image:
        payload["image"] = _image_payload(page.image_path, limits)
    else:
        payload.pop("image_path", None)
        payload["has_image"] = bool(page.image_path)
    return payload


def pages_payload(
    *,
    start_page: int,
    end_page: int,
    document_id: int | None = None,
    include_images: bool = False,
) -> dict[str, Any]:
    limits = _context_limits()
    doc_id = _require_active_document_id(document_id)
    if end_page - start_page + 1 > limits.maximum_explicit_pages:
        raise ResearchMarkerError(
            f"Requested too many pages. Limit is {limits.maximum_explicit_pages}.",
            details={"start_page": start_page, "end_page": end_page},
        )
    pages = get_pages(
        doc_id,
        int(start_page),
        int(end_page),
        include_images=include_images,
    )
    serialized = []
    images_attached = 0
    for page in pages:
        item = page.to_dict(expose_local_path=True)
        if include_images and images_attached < limits.maximum_page_images:
            image = _image_payload(page.image_path, limits)
            if image:
                item["image"] = image
                images_attached += 1
            else:
                item.pop("image_path", None)
                item["has_image"] = bool(page.image_path)
        else:
            item.pop("image_path", None)
            item["has_image"] = bool(page.image_path)
        serialized.append(item)
    return {
        "document_id": doc_id,
        "start_page": start_page,
        "end_page": end_page,
        "pages": serialized,
    }


def selection_payload() -> dict[str, Any]:
    selection = get_current_selection()
    if not selection:
        return {"active": False, "message": "No text is currently selected in Research Marker."}
    return {"active": True, **selection}


def search_payload(
    *,
    query: str,
    document_id: int | None = None,
    limit: int = 6,
) -> dict[str, Any]:
    limits = _context_limits()
    doc_id = _require_active_document_id(document_id)
    capped = max(1, min(int(limit or limits.maximum_retrieved_chunks), limits.maximum_retrieved_chunks))
    chunks = search_document(doc_id, query, limit=capped)
    return {
        "document_id": doc_id,
        "query": query,
        "chunks": [
            {
                "chunk_id": chunk.chunk_id,
                "start_page": chunk.start_page,
                "end_page": chunk.end_page,
                "section_title": chunk.section_title,
                "score": chunk.score,
                "text": chunk.chunk_text,
            }
            for chunk in chunks
        ],
    }


def resolve_question_payload(
    *,
    question: str,
    document_id: int | None = None,
    include_page_image: bool = True,
) -> dict[str, Any]:
    limits = _context_limits()
    state = get_active_context()
    doc_id = _require_active_document_id(document_id)
    context = build_paper_context(
        document_id=doc_id,
        question=question,
        current_page=state.current_page,
        selected_text=state.selected_text or "",
        selected_text_page=state.selected_text_page,
        include_page_image=include_page_image,
        limits=limits,
    )
    images = []
    for path in context.page_images[: limits.maximum_page_images]:
        image = _image_payload(path, limits)
        if image:
            images.append(image)
    return {
        "document_id": context.document_id,
        "document_title": context.document_title,
        "normalized_question": context.user_question,
        "referenced_pages": context.referenced_pages,
        "current_page": context.current_page,
        "retrieval_confidence": context.retrieval_confidence,
        "formatted_context": format_paper_context(context),
        "images": images,
        "page_count_in_context": len(context.page_text),
        "chunk_count": len(context.retrieved_chunks),
    }
