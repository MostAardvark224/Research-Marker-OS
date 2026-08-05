from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from threading import RLock

from django.db import connection

from api import models
from api.errors import DocumentNotFound, PageOutOfRange
from .ingestion import ensure_document_ingested
from .types import PageContext, RetrievedChunk


@dataclass(slots=True)
class ActiveReaderState:
    document_id: int | None = None
    document_title: str = ""
    current_page: int | None = None
    selected_text: str = ""
    selected_text_page: int | None = None
    last_updated: str = ""


_STATE = ActiveReaderState()
_STATE_LOCK = RLock()


def update_active_context(
    *,
    document_id: int | None,
    document_title: str = "",
    current_page: int | None = None,
    selected_text: str = "",
    selected_text_page: int | None = None,
) -> ActiveReaderState:
    with _STATE_LOCK:
        _STATE.document_id = document_id
        _STATE.document_title = document_title
        _STATE.current_page = current_page
        _STATE.selected_text = selected_text
        _STATE.selected_text_page = selected_text_page
        _STATE.last_updated = datetime.now(timezone.utc).isoformat()
        return ActiveReaderState(
            document_id=_STATE.document_id,
            document_title=_STATE.document_title,
            current_page=_STATE.current_page,
            selected_text=_STATE.selected_text,
            selected_text_page=_STATE.selected_text_page,
            last_updated=_STATE.last_updated,
        )


def get_active_context() -> ActiveReaderState:
    with _STATE_LOCK:
        return ActiveReaderState(
            document_id=_STATE.document_id,
            document_title=_STATE.document_title,
            current_page=_STATE.current_page,
            selected_text=_STATE.selected_text,
            selected_text_page=_STATE.selected_text_page,
            last_updated=_STATE.last_updated,
        )


def get_active_document() -> dict | None:
    state = get_active_context()
    if state.document_id is None:
        return None
    try:
        document = models.Document.objects.get(pk=state.document_id)
    except models.Document.DoesNotExist:
        return None
    return {
        "document_id": document.id,
        "document_hash": document.document_hash,
        "document_title": document.title,
        "page_count": document.page_count,
    }


def _to_page_context(page: models.DocumentPage, *, include_image: bool, reason: str) -> PageContext:
    return PageContext(
        document_id=page.document_id,
        document_hash=page.document.document_hash,
        document_title=page.document.title,
        page_number=page.page_number,
        text=page.extracted_text,
        text_blocks=page.text_blocks or [],
        source_type=page.source_type,
        ocr_used=page.ocr_used,
        ocr_confidence=page.ocr_confidence,
        visually_complex=page.visually_complex,
        image_path=page.page_image_path if include_image and page.page_image_path else None,
        context_reason=reason,
    )


def get_page(
    document_id: int,
    page_number: int,
    *,
    include_image: bool = False,
    reason: str = "explicit_page_reference",
) -> PageContext:
    document = ensure_document_ingested(document_id)
    if page_number < 1 or page_number > document.page_count:
        raise PageOutOfRange(
            f"Page {page_number} is outside this document's page range (1–{document.page_count}).",
            details={"page_number": page_number, "page_count": document.page_count},
        )
    try:
        page = document.context_pages.select_related("document").get(page_number=page_number)
    except models.DocumentPage.DoesNotExist as exc:
        raise PageOutOfRange(
            f"Page {page_number} has not been ingested.",
            details={"page_number": page_number, "page_count": document.page_count},
        ) from exc
    return _to_page_context(page, include_image=include_image, reason=reason)


def get_pages(
    document_id: int,
    start_page: int,
    end_page: int,
    *,
    include_images: bool = False,
) -> list[PageContext]:
    document = ensure_document_ingested(document_id)
    if start_page < 1 or end_page < start_page or end_page > document.page_count:
        raise PageOutOfRange(
            f"Requested page range {start_page}–{end_page} is invalid for a {document.page_count}-page document.",
            details={
                "start_page": start_page,
                "end_page": end_page,
                "page_count": document.page_count,
            },
        )
    return [
        _to_page_context(page, include_image=include_images, reason="explicit_page_reference")
        for page in document.context_pages.select_related("document").filter(
            page_number__gte=start_page,
            page_number__lte=end_page,
        )
    ]


def get_current_page(*, include_image: bool = False) -> PageContext | None:
    state = get_active_context()
    if state.document_id is None or state.current_page is None:
        return None
    return get_page(
        state.document_id,
        state.current_page,
        include_image=include_image,
        reason="current_page",
    )


def get_current_selection() -> dict | None:
    state = get_active_context()
    if not state.selected_text:
        return None
    return {
        "document_id": state.document_id,
        "page_number": state.selected_text_page,
        "text": state.selected_text,
        "source_type": "selection",
    }


def _fallback_search(document_id: int, query: str, limit: int) -> list[RetrievedChunk]:
    terms = set(re.findall(r"\w+", query.lower()))
    scored: list[tuple[float, models.DocumentChunk]] = []
    for chunk in models.DocumentChunk.objects.filter(document_id=document_id):
        chunk_terms = set(re.findall(r"\w+", chunk.normalized_text))
        overlap = len(terms & chunk_terms)
        if overlap:
            scored.append((overlap / max(len(terms), 1), chunk))
    scored.sort(key=lambda item: (-item[0], item[1].start_page))
    return [
        RetrievedChunk(
            document_id=chunk.document_id,
            chunk_id=chunk.chunk_id,
            start_page=chunk.start_page,
            end_page=chunk.end_page,
            chunk_text=chunk.chunk_text,
            section_title=chunk.section_title,
            score=score,
        )
        for score, chunk in scored[:limit]
    ]


def search_document(document_id: int, query: str, limit: int = 6) -> list[RetrievedChunk]:
    ensure_document_ingested(document_id)
    tokens = re.findall(r"[\w-]+", query)
    if not tokens:
        return []
    fts_query = " OR ".join(f'"{token.replace(chr(34), "")}"' for token in tokens[:20])
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT chunk_id, bm25(api_documentchunk_fts) AS score
                FROM api_documentchunk_fts
                WHERE api_documentchunk_fts MATCH %s AND document_id = %s
                ORDER BY score
                LIMIT %s
                """,
                [fts_query, document_id, max(1, min(limit, 50))],
            )
            matches = list(cursor.fetchall())
        chunks = {
            chunk.chunk_id: chunk
            for chunk in models.DocumentChunk.objects.filter(
                chunk_id__in=[row[0] for row in matches],
                document_id=document_id,
            )
        }
        results: list[RetrievedChunk] = []
        for chunk_id, raw_score in matches:
            chunk = chunks.get(chunk_id)
            if not chunk:
                continue
            results.append(
                RetrievedChunk(
                    document_id=chunk.document_id,
                    chunk_id=chunk.chunk_id,
                    start_page=chunk.start_page,
                    end_page=chunk.end_page,
                    chunk_text=chunk.chunk_text,
                    section_title=chunk.section_title,
                    score=1.0 / (1.0 + abs(float(raw_score))),
                )
            )
        return results
    except Exception:
        return _fallback_search(document_id, query, limit)


def get_figure_context(
    document_id: int,
    page_number: int,
    figure_label: str | None = None,
) -> dict:
    page = get_page(
        document_id,
        page_number,
        include_image=True,
        reason="figure_request",
    )
    blocks = page.text_blocks
    if figure_label:
        pattern = re.compile(re.escape(figure_label), re.IGNORECASE)
        matching = [block for block in blocks if pattern.search(block.get("text", ""))]
    else:
        matching = [
            block
            for block in blocks
            if re.search(r"\b(fig(?:ure)?\.?|table)\s*\d+", block.get("text", ""), re.IGNORECASE)
        ]
    return {
        "document_id": page.document_id,
        "document_title": page.document_title,
        "page_number": page.page_number,
        "text": page.text,
        "matching_blocks": matching,
        "image_path": page.image_path,
        "source_type": page.source_type,
        "ocr_used": page.ocr_used,
        "has_image": bool(page.image_path),
    }
