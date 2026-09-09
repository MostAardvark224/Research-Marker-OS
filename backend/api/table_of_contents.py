from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import fitz
from django.utils import timezone

from api.models import Document

MAX_TOC_DEPTH = 12
MAX_TOC_ITEMS = 1000
MAX_TOC_TITLE_LENGTH = 500


def _build_toc_tree(entries: list[list[Any]], page_count: int) -> list[dict[str, Any]]:
    roots: list[dict[str, Any]] = []
    parents: list[dict[str, Any]] = []

    for index, entry in enumerate(entries):
        if len(entry) < 3:
            continue
        try:
            requested_level = max(1, int(entry[0]))
            page = int(entry[2])
        except (TypeError, ValueError):
            continue

        title = str(entry[1] or "").strip()
        if not title or page < 1 or page > page_count:
            continue

        level = min(requested_level, len(parents) + 1, MAX_TOC_DEPTH)
        node = {
            "id": f"toc-{index}",
            "title": title[:MAX_TOC_TITLE_LENGTH],
            "page": page,
            "children": [],
        }

        if level == 1:
            roots.append(node)
        else:
            parents[level - 2]["children"].append(node)

        parents = parents[: level - 1]
        parents.append(node)

    return roots


def extract_document_table_of_contents(file_path: str | Path) -> tuple[list[dict[str, Any]], int]:
    with fitz.open(str(file_path)) as pdf:
        page_count = pdf.page_count
        return _build_toc_tree(pdf.get_toc(simple=True), page_count), page_count


def sanitize_table_of_contents(
    items: Any,
    *,
    page_count: int = 0,
    depth: int = 0,
    counter: list[int] | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        raise ValueError("Table of contents must be a list.")
    if not items:
        return []
    if depth >= MAX_TOC_DEPTH:
        raise ValueError(f"Table of contents cannot exceed {MAX_TOC_DEPTH} levels.")

    counter = counter if counter is not None else [0]
    sanitized = []
    for item in items:
        counter[0] += 1
        if counter[0] > MAX_TOC_ITEMS:
            raise ValueError(f"Table of contents cannot exceed {MAX_TOC_ITEMS} entries.")
        if not isinstance(item, dict):
            raise ValueError("Every table of contents entry must be an object.")

        title = str(item.get("title") or "").strip()
        if not title:
            raise ValueError("Every table of contents entry needs a title.")
        if len(title) > MAX_TOC_TITLE_LENGTH:
            raise ValueError(
                f"Table of contents titles cannot exceed {MAX_TOC_TITLE_LENGTH} characters."
            )

        try:
            page = int(item.get("page"))
        except (TypeError, ValueError) as exc:
            raise ValueError(f'"{title}" needs a valid PDF page number.') from exc
        if page < 1 or (page_count and page > page_count):
            maximum = f" and {page_count}" if page_count else ""
            raise ValueError(f'"{title}" page must be between 1{maximum}.')

        item_id = str(item.get("id") or uuid.uuid4())[:100]
        sanitized.append(
            {
                "id": item_id,
                "title": title,
                "page": page,
                "children": sanitize_table_of_contents(
                    item.get("children", []),
                    page_count=page_count,
                    depth=depth + 1,
                    counter=counter,
                ),
            }
        )
    return sanitized


def scrape_document_table_of_contents(document_id: int) -> None:
    try:
        document = Document.objects.get(pk=document_id)
    except Document.DoesNotExist:
        print(f"TOC scrape skipped: document {document_id} no longer exists.")
        return

    document.toc_status = Document.TocStatus.PROCESSING
    document.toc_error = ""
    document.toc_started_at = timezone.now()
    document.toc_completed_at = None
    document.save(
        update_fields=[
            "toc_status",
            "toc_error",
            "toc_started_at",
            "toc_completed_at",
        ]
    )

    try:
        if not document.file:
            raise ValueError("Document has no PDF file.")
        toc_data, page_count = extract_document_table_of_contents(document.file.path)
        document.toc_data = toc_data
        document.toc_source = "embedded"
        document.toc_status = Document.TocStatus.SUCCEEDED
        document.toc_error = ""
        document.toc_completed_at = timezone.now()
        if not document.page_count:
            document.page_count = page_count
        document.save(
            update_fields=[
                "toc_data",
                "toc_source",
                "toc_status",
                "toc_error",
                "toc_completed_at",
                "page_count",
            ]
        )
    except Exception as exc:
        document.toc_status = Document.TocStatus.FAILED
        document.toc_error = str(exc)[:2000]
        document.toc_completed_at = timezone.now()
        document.save(
            update_fields=["toc_status", "toc_error", "toc_completed_at"]
        )
        print(f"TOC scrape failed for document {document_id}: {exc}")
