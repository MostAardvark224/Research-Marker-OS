from __future__ import annotations

import re
from typing import Any

from django.db import transaction

from api import models
from api.ai import generate_colors


class SmartCollectionActionError(ValueError):
    def __init__(self, message: str, *, code: str = "invalid_smart_collection_action"):
        super().__init__(message)
        self.code = code


def _ready_collection() -> models.SmartCollections:
    collection = models.SmartCollections.objects.first()
    if collection is None or not collection.is_ready:
        raise SmartCollectionActionError(
            "Build a Smart Collection before editing topics.",
            code="collection_not_ready",
        )
    return collection


def _unique_folder_name(name: str, parent_id: int | None = None) -> str:
    base = re.sub(r"\s+", " ", name or "").strip() or "Topic"
    candidate = base[:255]
    suffix = 2
    while models.Folder.objects.filter(name=candidate, parent_id=parent_id).exists():
        extra = f" ({suffix})"
        candidate = f"{base[: 255 - len(extra)]}{extra}"
        suffix += 1
    return candidate


def _relabel_collection_topics(
    collection: models.SmartCollections, mapping: dict[str, str]
) -> None:
    if not mapping:
        return
    topics = []
    for topic in collection.topics or []:
        name = str(topic.get("name") or "")
        topic = dict(topic)
        topic["name"] = mapping.get(name, name)
        topics.append(topic)
    collection.topics = topics
    colors = collection.colors or {}
    collection.colors = {
        mapping.get(str(key), str(key)): value for key, value in colors.items()
    }
    ghosts = []
    for ghost in collection.ghost_nodes or []:
        ghost = dict(ghost)
        cluster = str(ghost.get("cluster") or "")
        ghost["cluster"] = mapping.get(cluster, cluster)
        ghosts.append(ghost)
    collection.ghost_nodes = ghosts
    recommendations = collection.reading_recommendations
    if isinstance(recommendations, dict) and isinstance(recommendations.get("items"), list):
        items = []
        for item in recommendations["items"]:
            if not isinstance(item, dict):
                items.append(item)
                continue
            updated = dict(item)
            cluster = str(updated.get("cluster") or "")
            updated["cluster"] = mapping.get(cluster, cluster)
            items.append(updated)
        recommendations = dict(recommendations)
        recommendations["items"] = items
        collection.reading_recommendations = recommendations
    stats = dict(collection.stats or {})
    thin = []
    for name in stats.get("thin_topics") or []:
        thin.append(mapping.get(str(name), str(name)))
    if thin:
        stats["thin_topics"] = thin
        collection.stats = stats


def rename_topic(from_name: str, to_name: str) -> dict[str, Any]:
    collection = _ready_collection()
    source = re.sub(r"\s+", " ", from_name or "").strip()
    target = re.sub(r"\s+", " ", to_name or "").strip()
    if not source or not target:
        raise SmartCollectionActionError("Provide both the current and new topic names.")
    if len(target) > 100:
        raise SmartCollectionActionError("Topic names must be 100 characters or fewer.")
    papers = list(
        models.Annotations.objects.filter(pk__in=collection.annotation_ids or [])
    )
    if not any((item.major_topic or "") == source for item in papers):
        raise SmartCollectionActionError(f'Topic "{source}" was not found.')
    if source == target:
        from api.smart_collections.service import serialize_collection

        return serialize_collection(collection)

    with transaction.atomic():
        for item in papers:
            fields = []
            if (item.major_topic or "") == source:
                item.major_topic = target
                fields.append("major_topic")
            if (item.pinned_topic or "") == source:
                item.pinned_topic = target
                fields.append("pinned_topic")
            if fields:
                item.save(update_fields=fields)
        _relabel_collection_topics(collection, {source: target})
        collection.save()
    from api.smart_collections.service import serialize_collection

    return serialize_collection(collection)


def move_papers(annotation_ids: list[int], topic: str, *, pin: bool = True) -> dict[str, Any]:
    collection = _ready_collection()
    target = re.sub(r"\s+", " ", topic or "").strip()
    if not target:
        raise SmartCollectionActionError("Provide a destination topic.")
    ids = [int(item) for item in annotation_ids or []]
    if not ids:
        raise SmartCollectionActionError("Select at least one paper to move.")
    allowed = set(int(item) for item in collection.annotation_ids or [])
    wanted = set(ids)
    papers = list(models.Annotations.objects.filter(pk__in=wanted).select_related("document"))
    if {item.id for item in papers} != wanted or not wanted <= allowed:
        raise SmartCollectionActionError("One or more papers are not in this collection.")

    with transaction.atomic():
        for item in papers:
            item.major_topic = target
            item.sub_topic = None
            item.pinned_topic = target if pin else ""
            item.save(update_fields=["major_topic", "sub_topic", "pinned_topic"])
        _rebuild_topic_summaries(collection)
        collection.save()
    from api.smart_collections.service import serialize_collection

    return serialize_collection(collection)


def merge_topics(source_names: list[str], target_name: str) -> dict[str, Any]:
    collection = _ready_collection()
    target = re.sub(r"\s+", " ", target_name or "").strip()
    sources = [
        re.sub(r"\s+", " ", name or "").strip()
        for name in source_names or []
        if re.sub(r"\s+", " ", name or "").strip()
    ]
    if not target or not sources:
        raise SmartCollectionActionError("Provide topics to merge and a destination name.")
    names = set(sources + [target])
    papers = list(
        models.Annotations.objects.filter(pk__in=collection.annotation_ids or [])
    )
    present = {item.major_topic or "" for item in papers}
    missing = [name for name in names if name not in present and name != target]
    if missing:
        raise SmartCollectionActionError(f'Topic "{missing[0]}" was not found.')

    mapping = {name: target for name in sources if name != target}
    with transaction.atomic():
        for item in papers:
            fields = []
            if (item.major_topic or "") in mapping:
                item.major_topic = target
                item.sub_topic = None
                fields.extend(["major_topic", "sub_topic"])
            if (item.pinned_topic or "") in mapping:
                item.pinned_topic = target
                fields.append("pinned_topic")
            if fields:
                item.save(update_fields=list(dict.fromkeys(fields)))
        _relabel_collection_topics(collection, mapping)
        _rebuild_topic_summaries(collection)
        collection.save()
    from api.smart_collections.service import serialize_collection

    return serialize_collection(collection)


def save_topic_as_folder(topic_name: str) -> dict[str, Any]:
    collection = _ready_collection()
    name = re.sub(r"\s+", " ", topic_name or "").strip()
    if not name:
        raise SmartCollectionActionError("Provide a topic to save as a folder.")
    papers = list(
        models.Annotations.objects.filter(
            pk__in=collection.annotation_ids or [],
            major_topic=name,
        ).select_related("document")
    )
    if not papers:
        raise SmartCollectionActionError(f'Topic "{name}" has no papers to save.')

    from api.views import _next_document_sort_order, _next_folder_sort_order

    folder_name = _unique_folder_name(name)
    with transaction.atomic():
        folder = models.Folder.objects.create(
            name=folder_name,
            parent=None,
            sort_order=_next_folder_sort_order(None),
        )
        sort_start = _next_document_sort_order(folder.pk)
        for offset, item in enumerate(papers):
            document = item.document
            document.folder = folder
            document.sort_order = sort_start + offset
            document.save(update_fields=["folder", "sort_order"])
    from api.smart_collections.service import serialize_collection

    payload = serialize_collection(collection)
    payload["folder"] = {"id": folder.pk, "name": folder.name, "count": len(papers)}
    return payload


def download_arxiv_paper(
    arxiv_id: str,
    *,
    title: str = "",
    auto_folder: bool = True,
) -> tuple[models.Document, bool]:
    from api.arxiv import fetch_arxiv_metadata, parse_arxiv_id
    from api.views import _apply_ocr_settings_to_document, _stream_pdf_to_document

    parsed = parse_arxiv_id(str(arxiv_id or "").strip()) or str(arxiv_id or "").strip()
    if not parsed:
        raise SmartCollectionActionError("Provide a valid arXiv id.", code="invalid_arxiv_id")
    metadata = fetch_arxiv_metadata(parsed)
    if not metadata or not metadata.get("pdf_url"):
        raise SmartCollectionActionError(
            "Could not fetch that arXiv paper.",
            code="arxiv_unavailable",
        )
    paper_title = (title or metadata.get("title") or parsed).strip()
    existing = _existing_document(paper_title, parsed)
    if existing is not None:
        return existing, True
    folder = _recommended_folder() if auto_folder else None
    document = _stream_pdf_to_document(metadata["pdf_url"], paper_title, folder)
    _apply_ocr_settings_to_document(document, True, "paddleocr")
    models.Annotations.objects.get_or_create(
        document=document,
        defaults={"highlight_data": [], "sticky_note_data": [], "notepad": ""},
    )
    return document, False


def import_arxiv_candidate(
    arxiv_id: str,
    *,
    title: str = "",
    auto_folder: bool = True,
) -> dict[str, Any]:
    document, already = download_arxiv_paper(
        arxiv_id, title=title, auto_folder=auto_folder
    )
    from api.arxiv import parse_arxiv_id

    marked_id = parse_arxiv_id(str(arxiv_id or "").strip()) or str(arxiv_id or "").strip()
    _mark_recommendation_imported(marked_id, document)
    from api.smart_collections.service import serialize_collection

    collection = models.SmartCollections.objects.first()
    payload = serialize_collection(collection) if collection and collection.is_ready else {}
    payload["imported"] = {
        "document_id": document.pk,
        "title": document.title,
        "already_in_library": already,
    }
    return payload


def _recommended_folder() -> models.Folder:
    from api.views import _next_folder_sort_order

    folder = models.Folder.objects.filter(name="Recommended Reads", parent=None).first()
    if folder:
        return folder
    return models.Folder.objects.create(
        name="Recommended Reads",
        parent=None,
        sort_order=_next_folder_sort_order(None),
    )


def _existing_document(title: str, arxiv_id: str) -> models.Document | None:
    cleaned = re.sub(r"\s+", " ", title or "").strip()
    if cleaned:
        match = models.Document.objects.filter(title__iexact=cleaned).first()
        if match:
            return match
    needle = str(arxiv_id or "").strip()
    if needle:
        return models.Document.objects.filter(title__icontains=needle).first()
    return None


def _mark_recommendation_imported(arxiv_id: str, document: models.Document) -> None:
    collection = models.SmartCollections.objects.first()
    if collection is None:
        return
    recommendations = collection.reading_recommendations
    if not isinstance(recommendations, dict):
        return
    items = recommendations.get("items")
    if not isinstance(items, list):
        return
    changed = False
    for item in items:
        if not isinstance(item, dict):
            continue
        for candidate in item.get("candidates") or []:
            if not isinstance(candidate, dict):
                continue
            if str(candidate.get("arxiv_id") or "") != str(arxiv_id):
                continue
            candidate["imported"] = True
            candidate["already_in_library"] = True
            candidate["document_id"] = document.pk
            changed = True
    ghosts = []
    for ghost in collection.ghost_nodes or []:
        ghost = dict(ghost)
        if str(ghost.get("arxiv_id") or "") == str(arxiv_id):
            ghost["imported"] = True
            ghost["document_id"] = document.pk
            changed = True
        ghosts.append(ghost)
    if changed:
        collection.ghost_nodes = ghosts
        collection.reading_recommendations = recommendations
        collection.save(
            update_fields=["ghost_nodes", "reading_recommendations", "updated_at"]
        )


def _rebuild_topic_summaries(collection: models.SmartCollections) -> None:
    papers = list(
        models.Annotations.objects.filter(pk__in=collection.annotation_ids or [])
        .select_related("document")
        .order_by("id")
    )
    grouped: dict[str, list[models.Annotations]] = {}
    for item in papers:
        grouped.setdefault(item.major_topic or "Uncategorized", []).append(item)
    topics = []
    existing = {str(topic.get("name")): topic for topic in collection.topics or []}
    for name, members in grouped.items():
        previous = existing.get(name) or {}
        xs = [float(item.x_coordinate or 0) for item in members]
        ys = [float(item.y_coordinate or 0) for item in members]
        topics.append(
            {
                "name": name,
                "count": len(members),
                "paper_ids": [item.id for item in members],
                "cohesion": previous.get("cohesion", 0),
                "pillar_ids": [
                    item.id for item in members if (item.node_role or "") == "pillar"
                ],
                "x": round(sum(xs) / max(len(xs), 1), 4),
                "y": round(sum(ys) / max(len(ys), 1), 4),
                "thin_notes": previous.get("thin_notes", False),
            }
        )
    topics.sort(key=lambda item: (0 if item["name"] != "Uncategorized" else 1, item["name"]))
    collection.topics = topics
    collection.colors = generate_colors([topic["name"] for topic in topics])
    stats = dict(collection.stats or {})
    stats["topic_count"] = len([topic for topic in topics if topic["name"] != "Uncategorized"])
    stats["uncategorized"] = next(
        (topic["count"] for topic in topics if topic["name"] == "Uncategorized"), 0
    )
    collection.stats = stats
