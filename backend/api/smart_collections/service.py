from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
import json
import logging
import re
from typing import Any

from django.db import transaction
from django.utils import timezone
import numpy as np
import requests
from tenacity import (
    Retrying,
    retry_if_exception,
    stop_after_attempt,
    wait_random_exponential,
)

from api import models
from api.ai import (
    generate_colors,
    get_provider_api_key,
    get_provider_base_url,
    send_prompt,
)
from api.errors import ResearchMarkerError
from api.providers.embeddings import (
    EMBEDDING_PIPELINE_VERSION,
    EmbeddingSpec,
    build_embedding_provider,
)
from api.utils import load_env_vars
from .config import SmartCollectionConfig


LOGGER = logging.getLogger(__name__)
MAX_ANNOTATIONS = 2000
MAX_AUTO_IMPORTS = 3
MAX_GHOST_NODES = 8
THIN_NOTE_CHARS = 180
# Jobs that never leave the queue usually mean the django-q worker is down.
QUEUED_STALE_AFTER = timedelta(minutes=2)
# Running jobs heartbeat on stage/batch progress; silence longer than this is a hang.
RUNNING_STALE_AFTER = timedelta(minutes=8)
# Back-compat alias for callers/tests that still reference the old name.
STALE_JOB_AFTER = RUNNING_STALE_AFTER
LABEL_MAX_LENGTH = 100

STAGE_LABELS: dict[str, str] = {
    "queued": "Waiting for background worker",
    "preflight": "Checking configuration",
    "embedding": "Embedding annotations",
    "clustering": "Clustering related notes",
    "labeling": "Labeling topics",
    "projection": "Building the graph layout",
    "similarity": "Finding similar papers",
    "discovery": "Finding knowledge gaps",
    "recommendations": "Generating reading recommendations",
    "publishing": "Saving the collection",
    "completed": "Completed",
    "failed": "Failed",
    "cancelled": "Cancelled",
}


class SmartCollectionCancelled(Exception):
    pass


def stage_label(stage: str | None) -> str:
    key = str(stage or "").strip()
    if not key:
        return "Working"
    return STAGE_LABELS.get(key, key.replace("_", " ").capitalize())


def serialize_job(job: models.SmartCollectionJob) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "task_id": job.task_id,
        "status": job.status,
        "stage": job.stage,
        "stage_label": stage_label(job.stage),
        "progress": job.progress,
        "embedding_provider": job.embedding_provider,
        "embedding_model": job.embedding_model,
        "embedding_dimensions": job.embedding_dimensions,
        "generation_provider": job.generation_provider,
        "generation_model": job.generation_model,
        "total_items": job.total_items,
        "processed_items": job.processed_items,
        "warnings": job.warnings or [],
        "error": (
            {
                "code": job.error_code or "smart_collection_failed",
                "message": job.error_message or "Smart Collection generation failed.",
                "stage": job.stage or None,
                "stage_label": stage_label(job.stage),
            }
            if job.status == models.SmartCollectionJob.Status.FAILED
            else None
        ),
        "cancel_requested": job.cancel_requested,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "updated_at": job.updated_at,
    }


def _stale_failure_for(job: models.SmartCollectionJob) -> tuple[str, str]:
    stage = stage_label(job.stage)
    providers = (
        f"Embedding: {job.embedding_provider}/{job.embedding_model}. "
        f"Labels: {job.generation_provider}/{job.generation_model}."
    )
    worker_detail = _django_q_failure_detail(job)
    if job.status == models.SmartCollectionJob.Status.QUEUED:
        if worker_detail:
            return (
                "worker_failure",
                "Smart Collection never left the queue because the background "
                f"worker rejected the task: {worker_detail} ({providers})",
            )
        return (
            "worker_not_running",
            "Smart Collection stayed queued and never started. The background "
            "django-q worker is probably not running on this host. Start the "
            "worker process, then retry. "
            f"({providers})",
        )
    if job.stage in ("embedding", "preflight"):
        return (
            "embedding_timeout",
            f"Smart Collection stalled while {stage.lower()}. The embedding "
            "provider stopped responding or the worker died mid-request. Check "
            f"network access to the embedding API and retry. ({providers})",
        )
    if job.stage in ("labeling", "recommendations"):
        return (
            "generation_timeout",
            f"Smart Collection stalled while {stage.lower()}. The generation "
            "provider stopped responding. Verify the API key/model works from "
            f"this host and retry. ({providers})",
        )
    detail = f" Worker error: {worker_detail}." if worker_detail else ""
    return (
        "worker_timeout",
        f"Smart Collection stalled during '{stage}' with no progress. The "
        f"background worker may have crashed or frozen.{detail} Restart the "
        f"worker and retry. ({providers})",
    )


def _django_q_failure_detail(job: models.SmartCollectionJob) -> str:
    """Best-effort real error from django-q when the job row never advanced."""
    task_id = (job.task_id or "").strip()
    if not task_id:
        return ""
    try:
        from django_q.models import Task
    except Exception:
        return ""
    try:
        task = Task.objects.filter(id=task_id).only("success", "result").first()
    except Exception:
        return ""
    if task is None or task.success:
        return ""
    detail = str(task.result or "").strip()
    if not detail:
        return "task failed with no result"
    # django-q sometimes stores a long traceback string; keep the useful head.
    first_line = detail.splitlines()[0].strip()
    return first_line[:400]


def reconcile_stale_job(job: models.SmartCollectionJob) -> models.SmartCollectionJob:
    active = job.status in (
        models.SmartCollectionJob.Status.QUEUED,
        models.SmartCollectionJob.Status.RUNNING,
    )
    repair_stale_diagnosis = (
        job.status == models.SmartCollectionJob.Status.FAILED
        and job.error_code == "worker_not_running"
    )
    if not active and not repair_stale_diagnosis:
        return job

    # A completed django-q failure is definitive, even while the job's stale
    # timer is still running.  This also covers worker-level failures where the
    # result hook could not be imported in a frozen build.
    worker_detail = _django_q_failure_detail(job)
    if worker_detail:
        stage = job.stage or "queued"
        job.status = models.SmartCollectionJob.Status.FAILED
        job.error_code = "worker_failure"
        job.error_message = (
            f"The background worker rejected the Smart Collection task during "
            f"'{stage}': {worker_detail}"
        )
        job.finished_at = job.finished_at or timezone.now()
        job.save(
            update_fields=[
                "status",
                "error_code",
                "error_message",
                "finished_at",
                "updated_at",
            ]
        )
        return job

    if not active:
        return job

    if job.status == models.SmartCollectionJob.Status.QUEUED:
        threshold = QUEUED_STALE_AFTER
    else:
        threshold = RUNNING_STALE_AFTER

    if job.updated_at >= timezone.now() - threshold:
        return job

    code, message = _stale_failure_for(job)
    # Keep the last real stage so the UI can say where it stalled.
    job.status = models.SmartCollectionJob.Status.FAILED
    job.error_code = code
    job.error_message = message
    job.finished_at = timezone.now()
    job.save(
        update_fields=[
            "status",
            "error_code",
            "error_message",
            "finished_at",
            "updated_at",
        ]
    )
    return job


def _set_job(
    job: models.SmartCollectionJob,
    *,
    stage: str,
    progress: int,
    processed_items: int | None = None,
    warning: str | None = None,
) -> None:
    job.stage = stage
    job.progress = max(0, min(100, int(progress)))
    fields = ["stage", "progress", "updated_at"]
    if processed_items is not None:
        job.processed_items = processed_items
        fields.append("processed_items")
    if warning:
        warnings = list(job.warnings or [])
        if warning not in warnings:
            warnings.append(warning[:500])
        job.warnings = warnings
        fields.append("warnings")
    job.save(update_fields=fields)
    _check_cancelled(job)


def _check_cancelled(job: models.SmartCollectionJob) -> None:
    job.refresh_from_db(fields=["cancel_requested"])
    if job.cancel_requested:
        raise SmartCollectionCancelled()


def _list_items(data: Any) -> list[Any]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return list(data.values())
    return []


def _paper_opening_text(document_id: int, limit: int) -> str:
    parts: list[str] = []
    total = 0
    pages = (
        models.DocumentPage.objects.filter(document_id=document_id)
        .order_by("page_number")
        .values_list("extracted_text", flat=True)[:4]
    )
    for text in pages:
        cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
        if not cleaned:
            continue
        parts.append(cleaned)
        total += len(cleaned)
        if total >= limit:
            break
    return " ".join(parts)[:limit]


def _annotation_text(annotation: models.Annotations) -> str:
    notes = _notes_text(annotation)
    title = str(annotation.document.title if annotation.document_id else "")
    note_chars = max(0, len(notes) - len(title))
    # Thin notes carry little topical signal, so lean on the paper itself.
    limit = 4000 if note_chars < THIN_NOTE_CHARS else 1500
    opening = _paper_opening_text(annotation.document_id, limit)
    if not opening:
        return notes
    return f"{notes}\nPaper excerpt: {opening}"[:12_000]


def _notes_text(annotation: models.Annotations) -> str:
    sticky_parts: list[str] = []
    for item in _list_items(annotation.sticky_note_data):
        if not isinstance(item, dict):
            continue
        tag = str(item.get("tag") or "").strip()
        content = str(item.get("content") or "").strip()
        if tag and content:
            sticky_parts.append(f"[{tag}] {content}")
        elif content:
            sticky_parts.append(content)
    highlight_parts: list[str] = []
    for item in _list_items(annotation.highlight_data):
        if isinstance(item, dict):
            text = str(item.get("text") or "").strip()
            if text:
                highlight_parts.append(text)
        elif isinstance(item, str) and item.strip():
            highlight_parts.append(item.strip())
    return "\n".join(
        part
        for part in [
            f"Document: {annotation.document.title}",
            "Highlights: " + "\n".join(highlight_parts[:40]) if highlight_parts else "",
            "Sticky notes: " + "\n".join(sticky_parts) if sticky_parts else "",
            "Notepad: " + str(annotation.notepad or "").strip()
            if annotation.notepad
            else "",
        ]
        if part
    )[:12_000]


def _excerpt(annotation: models.Annotations, limit: int = 240) -> str:
    for item in _list_items(annotation.highlight_data):
        text = item.get("text") if isinstance(item, dict) else item
        cleaned = str(text or "").strip()
        if cleaned:
            return cleaned[:limit]
    for item in _list_items(annotation.sticky_note_data):
        if isinstance(item, dict):
            cleaned = str(item.get("content") or "").strip()
            if cleaned:
                return cleaned[:limit]
    return str(annotation.notepad or "").strip()[:limit]


def _note_chars(annotation: models.Annotations) -> int:
    title = str(annotation.document.title if annotation.document_id else "")
    return max(0, len(_notes_text(annotation)) - len(title))


def _standalone_note_text(note: models.StandaloneNote) -> str:
    return f"Standalone note: {note.title}\n{note.content}"[:12_000]


def _embedding_is_current(
    annotation: models.Annotations, spec: EmbeddingSpec
) -> bool:
    binary = annotation.embedding_binary
    byte_length = len(binary or b"")
    return bool(
        binary
        and not annotation.needs_embedding
        and annotation.content_hash == annotation.generate_content_hash()
        and annotation.embedding_provider == spec.provider
        and annotation.embedding_model == spec.model
        and annotation.embedding_dimensions == spec.dimensions
        and annotation.embedding_version == EMBEDDING_PIPELINE_VERSION
        and byte_length == spec.dimensions * np.dtype(np.float32).itemsize
    )


def _note_embedding_is_current(
    note: models.StandaloneNote, spec: EmbeddingSpec
) -> bool:
    binary = note.embedding_binary
    return bool(
        binary
        and not note.needs_embedding
        and note.content_hash == note.generate_content_hash()
        and note.embedding_provider == spec.provider
        and note.embedding_model == spec.model
        and note.embedding_dimensions == spec.dimensions
        and note.embedding_version == EMBEDDING_PIPELINE_VERSION
        and len(binary or b"") == spec.dimensions * np.dtype(np.float32).itemsize
    )


def embed_pending_annotations(
    config: SmartCollectionConfig | None = None,
) -> int:
    if config is None:
        from .config import get_smart_collection_config

        # Background embed worker only needs embedding credentials.
        config = get_smart_collection_config(require_generation=False)
    annotations = list(
        models.Annotations.objects.select_related("document").order_by("id")
    )
    provider = build_embedding_provider(config.embedding)
    stale = [
        annotation
        for annotation in annotations
        if not _embedding_is_current(annotation, config.embedding)
    ]
    updated = 0
    for start in range(0, len(stale), provider.batch_size):
        batch = stale[start : start + provider.batch_size]
        vectors = provider.embed_texts([_annotation_text(item) for item in batch])
        for item, vector in zip(batch, vectors, strict=True):
            item.embedding_binary = vector.tobytes()
            item.embedding_provider = config.embedding.provider
            item.embedding_model = config.embedding.model
            item.embedding_dimensions = config.embedding.dimensions
            item.embedding_version = EMBEDDING_PIPELINE_VERSION
            item.content_hash = item.generate_content_hash()
            item.needs_embedding = False
        models.Annotations.objects.bulk_update(
            batch,
            [
                "embedding_binary",
                "embedding_provider",
                "embedding_model",
                "embedding_dimensions",
                "embedding_version",
                "content_hash",
                "needs_embedding",
            ],
            batch_size=provider.batch_size,
        )
        updated += len(batch)
    notes = list(models.StandaloneNote.objects.order_by("id"))
    stale_notes = [note for note in notes if not _note_embedding_is_current(note, config.embedding)]
    for start in range(0, len(stale_notes), provider.batch_size):
        batch = stale_notes[start : start + provider.batch_size]
        vectors = provider.embed_texts([_standalone_note_text(item) for item in batch])
        for item, vector in zip(batch, vectors, strict=True):
            item.embedding_binary = vector.tobytes()
            item.embedding_provider = config.embedding.provider
            item.embedding_model = config.embedding.model
            item.embedding_dimensions = config.embedding.dimensions
            item.embedding_version = EMBEDDING_PIPELINE_VERSION
            item.content_hash = item.generate_content_hash()
            item.needs_embedding = False
        models.StandaloneNote.objects.bulk_update(
            batch,
            [
                "embedding_binary",
                "embedding_provider",
                "embedding_model",
                "embedding_dimensions",
                "embedding_version",
                "content_hash",
                "needs_embedding",
            ],
            batch_size=provider.batch_size,
        )
        updated += len(batch)
    return updated


def _embed_annotations(
    job: models.SmartCollectionJob,
    annotations: list[models.Annotations],
    spec: EmbeddingSpec,
) -> None:
    provider = build_embedding_provider(spec)
    stale = [item for item in annotations if not _embedding_is_current(item, spec)]
    if not stale:
        _set_job(job, stage="embedding", progress=25, processed_items=len(annotations))
        return

    completed = 0
    for start in range(0, len(stale), provider.batch_size):
        # Heartbeat before the provider call so a hung API request can be
        # detected as stale instead of looking like silent progress.
        progress = 5 + round(20 * completed / max(1, len(stale)))
        _set_job(
            job,
            stage="embedding",
            progress=progress,
            processed_items=min(len(annotations), completed),
        )
        batch = stale[start : start + provider.batch_size]
        vectors = provider.embed_texts([_annotation_text(item) for item in batch])
        for item, vector in zip(batch, vectors, strict=True):
            item.embedding_binary = vector.tobytes()
            item.embedding_provider = spec.provider
            item.embedding_model = spec.model
            item.embedding_dimensions = spec.dimensions
            item.embedding_version = EMBEDDING_PIPELINE_VERSION
            item.content_hash = item.generate_content_hash()
            item.needs_embedding = False
        models.Annotations.objects.bulk_update(
            batch,
            [
                "embedding_binary",
                "embedding_provider",
                "embedding_model",
                "embedding_dimensions",
                "embedding_version",
                "content_hash",
                "needs_embedding",
            ],
            batch_size=provider.batch_size,
        )
        completed += len(batch)
        progress = 5 + round(20 * completed / max(1, len(stale)))
        _set_job(
            job,
            stage="embedding",
            progress=progress,
            processed_items=min(len(annotations), completed),
        )


def _vectors_for(
    annotations: list[models.Annotations], spec: EmbeddingSpec
) -> tuple[list[int], np.ndarray]:
    ids: list[int] = []
    vectors: list[np.ndarray] = []
    for item in annotations:
        if not _embedding_is_current(item, spec):
            continue
        if item.embedding_binary is None:
            continue
        vector = np.frombuffer(item.embedding_binary, dtype=np.float32)
        if vector.shape != (spec.dimensions,) or not np.isfinite(vector).all():
            continue
        norm = float(np.linalg.norm(vector))
        if norm <= 0:
            continue
        ids.append(item.id)
        vectors.append((vector / norm).astype(np.float32, copy=False))
    if not vectors:
        raise ValueError("No valid embeddings were available after embedding completed.")
    return ids, np.stack(vectors).astype(np.float32, copy=False)


def _cluster(
    ids: list[int], matrix: np.ndarray
) -> tuple[dict[int, dict[str, int | None]], str]:
    from .clustering import cluster_embeddings_with_method

    return cluster_embeddings_with_method(ids, matrix)


_KEYWORD_NOISE = {
    "abstract", "arxiv", "chapter", "com", "department", "doi", "document",
    "edition", "et", "al", "excerpt", "figure", "http", "https", "introduction",
    "notepad", "org", "paper", "papers", "pdf", "pp", "press", "section",
    "sticky", "notes", "highlights", "table", "university", "vol", "www",
    "google", "deepmind", "microsoft", "inc", "llc", "email", "author", "authors",
    "corresponding", "proceedings", "conference", "journal", "copyright", "rights",
    "reserved", "preprint", "published", "eng", "mountain",
}


def _topic_keywords(texts_by_key: dict[str, str], limit: int = 3) -> dict[str, list[str]]:
    """Terms that distinguish each group from the others, via TF-IDF across groups."""
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer

    keys = [key for key, text in texts_by_key.items() if text.strip()]
    if not keys:
        return {}
    vectorizer = TfidfVectorizer(
        stop_words=sorted(ENGLISH_STOP_WORDS | _KEYWORD_NOISE),
        ngram_range=(1, 2),
        token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z\-]{2,}\b",
        sublinear_tf=True,
        max_df=0.8 if len(keys) >= 3 else 1.0,
    )
    try:
        weights = vectorizer.fit_transform([texts_by_key[key] for key in keys]).toarray()
    except ValueError:
        return {}
    vocabulary = vectorizer.get_feature_names_out()
    # Phrases ("black holes") name a topic better than their component words.
    weights = weights * np.array([1.6 if " " in term else 1.0 for term in vocabulary])
    keywords: dict[str, list[str]] = {}
    for row, key in enumerate(keys):
        chosen: list[str] = []
        for column in np.argsort(-weights[row]):
            if weights[row, column] <= 0 or len(chosen) >= limit:
                break
            term = str(vocabulary[column])
            words = set(term.split())
            if any(words & set(existing.split()) for existing in chosen):
                continue
            chosen.append(term)
        keywords[key] = chosen
    return keywords


def _keyword_label(terms: list[str], fallback: str) -> str:
    if not terms:
        return fallback
    return _sanitize_label(" & ".join(term.title() for term in terms[:2]), fallback)


def _representative_content(
    cluster_map: dict[int, dict[str, int | None]],
    annotations_by_id: dict[int, models.Annotations],
) -> tuple[dict[str, dict[str, list[str]]], dict[str, str]]:
    titles: dict[str, list[str]] = defaultdict(list)
    notes: dict[str, list[str]] = defaultdict(list)
    corpus: dict[str, list[str]] = defaultdict(list)
    fallback: dict[str, str] = {}
    for annotation_id in sorted(cluster_map):
        labels = cluster_map[annotation_id]
        annotation = annotations_by_id[annotation_id]
        title = annotation.document.title
        major = int(labels["major"] if labels["major"] is not None else -1)
        full_text = _annotation_text(annotation)
        excerpt = _excerpt(annotation, 400) or full_text[:800]
        document_text = f"{title} {title} {full_text[:3000]}"
        if major >= 0:
            key = f"major:{major}"
            fallback[key] = f"Research Topic {major + 1}"
            corpus[key].append(document_text)
            if title not in titles[key] and len(titles[key]) < 12:
                titles[key].append(title)
            if excerpt and len(notes[key]) < 4:
                notes[key].append(excerpt)
        sub = labels["sub"]
        if major >= 0 and sub is not None and int(sub) >= 0:
            key = f"sub:{major}:{int(sub)}"
            fallback[key] = f"Subtopic {int(sub) + 1}"
            corpus[key].append(document_text)
            if title not in titles[key] and len(titles[key]) < 8:
                titles[key].append(title)
            if excerpt and len(notes[key]) < 3:
                notes[key].append(excerpt)
    for level in ("major:", "sub:"):
        keywords = _topic_keywords(
            {key: " ".join(texts) for key, texts in corpus.items() if key.startswith(level)}
        )
        for key, terms in keywords.items():
            fallback[key] = _keyword_label(terms, fallback[key])
    fallback = _dedupe_labels({}, fallback)
    samples = {
        key: {"titles": titles[key], "notes": notes[key]}
        for key in fallback
    }
    return samples, fallback


def _quota_exhausted(exc: BaseException) -> bool:
    message = str(exc).lower()
    return "quota" in message and (
        "exceeded" in message or "exhausted" in message or "perday" in message
    )


def _retryable_generation_error(exc: BaseException) -> bool:
    from api.errors import ProviderRateLimited

    # Daily quotas don't recover within a retry window; retrying only burns time.
    if _quota_exhausted(exc):
        return False
    if isinstance(exc, ProviderRateLimited):
        return True
    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return True
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    message = str(exc).lower()
    return any(token in message for token in ("429", "rate limit", "timeout", "503", "502"))


def _generate(config: SmartCollectionConfig, prompt: str, system_prompt: str) -> str:
    retryer = Retrying(
        retry=retry_if_exception(_retryable_generation_error),
        wait=wait_random_exponential(multiplier=2, max=30),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    if config.generation_provider == "codex":
        from api.providers.codex import get_codex_provider

        return str(
            retryer(
                get_codex_provider().generate_text,
                prompt,
                system_prompt=system_prompt,
                model=config.generation_model,
            )
            or ""
        )

    env = load_env_vars()
    return str(
        retryer(
            send_prompt,
            provider=config.generation_provider,
            api_key=get_provider_api_key(config.generation_provider, env),
            model=config.generation_model,
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.2,
            base_url=get_provider_base_url(config.generation_provider, env),
        )
        or ""
    )


def _json_object(text: str) -> dict[str, Any]:
    cleaned = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        str(text or "").strip(),
        flags=re.IGNORECASE | re.MULTILINE,
    )
    value = json.loads(cleaned)
    if not isinstance(value, dict):
        raise ValueError("The model response was not a JSON object.")
    return value


def _sanitize_label(value: Any, fallback: str) -> str:
    label = re.sub(r"\s+", " ", str(value or "")).strip().strip("\"'`")
    label = label.rstrip(".")
    if not label:
        label = fallback
    return label[:LABEL_MAX_LENGTH]


def _dedupe_labels(labels: dict[str, str], fallback: dict[str, str]) -> dict[str, str]:
    used: set[str] = set()
    unique: dict[str, str] = {}
    for key in fallback:
        label = labels.get(key) or fallback[key]
        base = label
        suffix = 2
        while label.lower() in used:
            label = f"{base} {suffix}"[:LABEL_MAX_LENGTH]
            suffix += 1
        used.add(label.lower())
        unique[key] = label
    return unique


def _label_clusters(
    job: models.SmartCollectionJob,
    config: SmartCollectionConfig,
    samples: dict[str, dict[str, list[str]]],
    fallback: dict[str, str],
) -> tuple[dict[str, str], bool]:
    """Returns the labels and whether the generation provider's quota is exhausted."""
    if not samples:
        return fallback, False
    prompt = (
        "Label every cluster in the following JSON. Return one JSON object whose keys "
        "exactly match the input keys and whose values are concise 2-5 word academic "
        "research-area labels. Use the paper titles as the primary signal. Avoid generic "
        "names like Research, Papers, Miscellaneous, or Uncategorized. Return JSON only.\n\n"
        + json.dumps(samples, ensure_ascii=False)
    )
    try:
        generated = _json_object(
            _generate(
                config,
                prompt,
                "You label groups of research papers. Return valid JSON only.",
            )
        )
        labeled = {
            key: _sanitize_label(generated.get(key), fallback[key])
            for key in fallback
        }
        return _dedupe_labels(labeled, fallback), False
    except Exception as exc:
        LOGGER.warning("Smart Collection label generation failed: %s", exc)
        exhausted = _quota_exhausted(exc)
        _set_job(
            job,
            stage="labeling",
            progress=48,
            warning=(
                "Your AI provider's quota is used up, so topics were named from their "
                "keywords and gaps were found by searching arXiv. Run an update after "
                "the quota resets for AI-written labels."
                if exhausted
                else "AI topic labels were unavailable, so topics were named from their keywords."
            ),
        )
        return fallback, exhausted


def _apply_pins(
    topic_map: dict[int, dict[str, str | None]],
    annotations_by_id: dict[int, models.Annotations],
) -> None:
    for annotation_id, topics in topic_map.items():
        pinned = str(annotations_by_id[annotation_id].pinned_topic or "").strip()
        if not pinned:
            continue
        topics["major"] = _sanitize_label(pinned, pinned)
        topics["sub"] = None


def _topic_records(
    ids: list[int],
    topic_map: dict[int, dict[str, str | None]],
    coordinates: dict[int, list[float]],
    metrics: dict[int, Any],
    annotations_by_id: dict[int, models.Annotations],
    matrix: np.ndarray,
    method: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from .clustering import center_embeddings, cluster_cohesion, edge_threshold

    index_by_id = {annotation_id: index for index, annotation_id in enumerate(ids)}
    centered = center_embeddings(matrix)
    nearest = 1.0
    if len(ids) >= 2:
        similarity = centered @ centered.T
        np.fill_diagonal(similarity, -np.inf)
        nearest = max(float(np.mean(similarity.max(axis=1))), 1e-6)
    grouped: dict[str, list[int]] = defaultdict(list)
    for annotation_id in ids:
        grouped[str(topic_map[annotation_id]["major"])].append(annotation_id)

    topics: list[dict[str, Any]] = []
    thin_topics: list[str] = []
    uncategorized = 0
    for name, members in grouped.items():
        xs = [coordinates[item][0] for item in members]
        ys = [coordinates[item][1] for item in members]
        cohesion = 0.0
        if len(members) >= 2:
            intra = cluster_cohesion(centered, [index_by_id[item] for item in members])
            # 1.0 means members are as alike as a typical paper and its nearest neighbour.
            cohesion = max(0.0, min(1.0, intra / nearest))
        thin_count = sum(
            1 for item in members if _note_chars(annotations_by_id[item]) < THIN_NOTE_CHARS
        )
        thin = thin_count >= max(1, round(len(members) * 0.5))
        if thin and name != "Uncategorized":
            thin_topics.append(name)
        if name == "Uncategorized":
            uncategorized = len(members)
        topics.append(
            {
                "name": name,
                "count": len(members),
                "paper_ids": members,
                "cohesion": round(float(cohesion), 4),
                "pillar_ids": [
                    item
                    for item in members
                    if getattr(metrics[item], "role", "") == "pillar"
                ],
                "x": round(sum(xs) / max(len(xs), 1), 4),
                "y": round(sum(ys) / max(len(ys), 1), 4),
                "thin_notes": thin,
            }
        )
    topics.sort(key=lambda item: (0 if item["name"] != "Uncategorized" else 1, item["name"]))
    stats = {
        "paper_count": len(ids),
        "topic_count": len([topic for topic in topics if topic["name"] != "Uncategorized"]),
        "uncategorized": uncategorized,
        "uncategorized_pct": round(100.0 * uncategorized / max(len(ids), 1), 1),
        "thin_topics": thin_topics,
        "similarity_threshold": round(edge_threshold(matrix), 4),
        "algorithm": method,
    }
    return topics, stats


def _library_titles() -> set[str]:
    return {
        re.sub(r"\s+", " ", title or "").strip().lower()
        for title in models.Document.objects.values_list("title", flat=True)
    }


def _gap_context(
    topic_map: dict[int, dict[str, str | None]],
    annotations_by_id: dict[int, models.Annotations],
) -> dict[str, list[str]]:
    context: dict[str, list[str]] = defaultdict(list)
    for annotation_id in sorted(topic_map):
        major = str(topic_map[annotation_id]["major"])
        title = annotations_by_id[annotation_id].document.title
        if title not in context[major] and len(context[major]) < 8:
            context[major].append(title)
    return dict(context)


def _auto_import_candidate(candidate: dict[str, Any]) -> models.Document | None:
    from .actions import download_arxiv_paper

    document, _already = download_arxiv_paper(
        str(candidate.get("arxiv_id") or ""),
        title=str(candidate.get("title") or ""),
        auto_folder=True,
    )
    return document


def _fallback_gaps(
    context: dict[str, list[str]],
    keywords: dict[str, list[str]] | None = None,
) -> list[dict[str, Any]]:
    ranked = sorted(
        (item for item in context.items() if item[0] != "Uncategorized"),
        key=lambda item: -len(item[1]),
    )
    gaps = []
    for name, _titles in ranked[:5]:
        terms = (keywords or {}).get(name) or []
        query = " ".join(terms[:2]) or name
        gaps.append(
            {
                "topic": f"More on {name}",
                "query": query,
                "overview": f"Papers about {query} that are not in your library yet.",
                "cluster": name,
            }
        )
    return gaps


def _topic_name_keywords(
    topic_map: dict[int, dict[str, str | None]],
    annotations_by_id: dict[int, models.Annotations],
) -> dict[str, list[str]]:
    corpus: dict[str, list[str]] = defaultdict(list)
    for annotation_id, topics in topic_map.items():
        annotation = annotations_by_id[annotation_id]
        title = annotation.document.title
        corpus[str(topics["major"])].append(f"{title} {title} {_annotation_text(annotation)[:3000]}")
    return _topic_keywords({name: " ".join(texts) for name, texts in corpus.items()})


def _generate_gaps(
    job: models.SmartCollectionJob | None,
    config: SmartCollectionConfig,
    context: dict[str, list[str]],
) -> dict[str, Any]:
    prompt = (
        "The JSON is a user's existing paper clusters. Identify at most five adjacent "
        "knowledge gaps that would make their library more complete. Return JSON only "
        'of the form {"gaps":[{"topic":"","query":"short arxiv search","overview":"",'
        '"cluster":"existing cluster name or empty","anchor_titles":[]}]}. Queries must '
        "be specific enough to search arXiv.\n\n"
        + json.dumps(context, ensure_ascii=False)
    )
    try:
        return _json_object(
            _generate(
                config,
                prompt,
                "You find missing papers for a researcher. Return valid JSON only.",
            )
        )
    except Exception as exc:
        LOGGER.warning("Smart Collection discovery failed: %s", exc)
        if job is not None:
            _set_job(
                job,
                stage="discovery",
                progress=84,
                warning=(
                    "AI gap analysis was unavailable, so gaps were found by searching "
                    "arXiv for your existing topics instead."
                ),
            )
        return {}


def _build_discovery(
    job: models.SmartCollectionJob | None,
    config: SmartCollectionConfig,
    topic_map: dict[int, dict[str, str | None]],
    annotations_by_id: dict[int, models.Annotations],
    coordinates: dict[int, list[float]],
    ids: list[int],
    matrix: np.ndarray | None,
    *,
    auto_import: bool,
    use_generation: bool = True,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    from api.arxiv import search_arxiv
    from .clustering import place_ghost

    context = _gap_context(topic_map, annotations_by_id)
    generated: dict[str, Any] = {}
    if use_generation:
        generated = _generate_gaps(job, config, context)

    raw_gaps = generated.get("gaps")
    if not isinstance(raw_gaps, list) or not raw_gaps:
        raw_gaps = _fallback_gaps(context, _topic_name_keywords(topic_map, annotations_by_id))

    known_titles = _library_titles()
    centroids: dict[str, list[float]] = {}
    spreads: dict[str, float] = {}
    grouped: dict[str, list[int]] = defaultdict(list)
    for annotation_id in ids:
        name = str(topic_map[annotation_id]["major"])
        grouped[name].append(annotation_id)
    for name, members in grouped.items():
        xs = [coordinates[item][0] for item in members]
        ys = [coordinates[item][1] for item in members]
        centroids[name] = [sum(xs) / len(xs), sum(ys) / len(ys)]
        spreads[name] = max(
            float(np.std(xs) if len(xs) > 1 else 0.4),
            float(np.std(ys) if len(ys) > 1 else 0.4),
            0.35,
        )

    recommendations: list[dict[str, Any]] = []
    ghosts: list[dict[str, Any]] = []
    imported_count = 0
    used_arxiv: set[str] = set()

    for index, gap in enumerate(raw_gaps[:5]):
        if not isinstance(gap, dict):
            continue
        topic = _sanitize_label(gap.get("topic"), f"Adjacent Topic {index + 1}")
        query = re.sub(r"\s+", " ", str(gap.get("query") or topic)).strip()
        overview = re.sub(r"\s+", " ", str(gap.get("overview") or "")).strip()
        cluster = str(gap.get("cluster") or "").strip()
        if cluster not in centroids:
            cluster = next(iter(centroids), "Uncategorized")
        try:
            hits = search_arxiv(query, max_results=4)
        except Exception as exc:
            LOGGER.warning("arXiv search failed for %s: %s", query, exc)
            hits = []
            if job is not None:
                _set_job(
                    job,
                    stage="discovery",
                    progress=86,
                    warning="Some arXiv searches failed while locating knowledge gaps.",
                )

        candidates: list[dict[str, Any]] = []
        for hit in hits:
            arxiv_id = str(hit.get("arxiv_id") or "")
            title = str(hit.get("title") or "").strip()
            if not arxiv_id or arxiv_id in used_arxiv:
                continue
            used_arxiv.add(arxiv_id)
            already = re.sub(r"\s+", " ", title).strip().lower() in known_titles
            candidate = {
                "title": title,
                "arxiv_id": arxiv_id,
                "abstract": str(hit.get("abstract") or ""),
                "authors": str(hit.get("authors") or ""),
                "pdf_url": str(hit.get("pdf_url") or ""),
                "already_in_library": already,
                "imported": False,
                "document_id": None,
                "ghost_id": None,
            }
            if (
                auto_import
                and not already
                and imported_count < MAX_AUTO_IMPORTS
                and candidate["pdf_url"]
            ):
                try:
                    document = _auto_import_candidate(candidate)
                except Exception as exc:
                    LOGGER.warning("Auto-import failed for %s: %s", arxiv_id, exc)
                    document = None
                if document is not None:
                    candidate["imported"] = True
                    candidate["already_in_library"] = True
                    candidate["document_id"] = document.pk
                    imported_count += 1
                    known_titles.add(re.sub(r"\s+", " ", document.title).strip().lower())
            candidates.append(candidate)
            if len(candidates) >= 3:
                break

        ghost_id = None
        visible_hit = next(
            (item for item in candidates if not item.get("already_in_library") or item.get("imported")),
            candidates[0] if candidates else None,
        )
        if visible_hit and len(ghosts) < MAX_GHOST_NODES:
            ghost_id = f"ghost-{index + 1}"
            neighbor_ids = grouped.get(cluster) or ids[:5]
            neighbor_coords = [coordinates[item] for item in neighbor_ids[:6] if item in coordinates]
            if matrix is not None and visible_hit.get("title"):
                try:
                    provider = build_embedding_provider(config.embedding)
                    vector = provider.embed_texts(
                        [
                            f"{visible_hit['title']}\n{visible_hit.get('abstract') or ''}"[:8000]
                        ]
                    )[0]
                    norm = float(np.linalg.norm(vector))
                    if norm > 0:
                        ghost_vec = (vector / norm).astype(np.float32, copy=False)
                        sims = ghost_vec @ matrix.T
                        top = np.argsort(sims)[::-1][:5]
                        neighbor_coords = [coordinates[ids[int(i)]] for i in top if ids[int(i)] in coordinates]
                except Exception as exc:
                    LOGGER.warning("Ghost embedding failed: %s", exc)
            xy = place_ghost(
                neighbor_coords,
                centroids.get(cluster, [0.0, 0.0]),
                spreads.get(cluster, 0.5),
            )
            visible_hit["ghost_id"] = ghost_id
            ghosts.append(
                {
                    "id": ghost_id,
                    "title": visible_hit["title"],
                    "arxiv_id": visible_hit["arxiv_id"],
                    "abstract": visible_hit.get("abstract") or "",
                    "authors": visible_hit.get("authors") or "",
                    "query": query,
                    "cluster": cluster,
                    "overview": overview,
                    "x": round(xy[0], 4),
                    "y": round(xy[1], 4),
                    "imported": bool(visible_hit.get("imported")),
                    "document_id": visible_hit.get("document_id"),
                }
            )

        recommendations.append(
            {
                "id": f"gap-{index + 1}",
                "topic": topic,
                "overview": overview,
                "query": query,
                "cluster": cluster,
                "candidates": candidates,
            }
        )

    return {"items": recommendations, "auto_imported": imported_count}, ghosts


def serialize_collection(
    collection: models.SmartCollections | None,
    active_job: models.SmartCollectionJob | None = None,
) -> dict[str, Any]:
    payload = {
        "data": [],
        "papers": [],
        "colors": {},
        "recommendations": {},
        "topics": [],
        "ghosts": [],
        "heatmap": {},
        "stats": {},
        "active_job": serialize_job(active_job) if active_job else None,
    }
    if collection is None or not collection.is_ready:
        return payload

    annotations = list(
        models.Annotations.objects.filter(pk__in=collection.annotation_ids or [])
        .select_related("document", "document__folder")
        .order_by("id")
    )
    by_id = {item.id: item for item in annotations}
    papers: list[dict[str, Any]] = []
    for obj in annotations:
        similar_raw = obj.similar_papers or []
        similar_ids: list[int] = []
        for item in similar_raw:
            if isinstance(item, int):
                similar_ids.append(item)
            elif isinstance(item, dict) and item.get("id") is not None:
                try:
                    similar_ids.append(int(item["id"]))
                except (TypeError, ValueError):
                    continue
        papers.append(
            {
                "id": obj.pk,
                "document_id": obj.document_id,
                "doc_title": obj.document.title,
                "major_topic": obj.major_topic,
                "sub_topic": obj.sub_topic,
                "x_coordinate": obj.x_coordinate,
                "y_coordinate": obj.y_coordinate,
                "similar_papers": similar_ids,
                "similar": [
                    {
                        "id": neighbor_id,
                        "title": by_id[neighbor_id].document.title,
                        "document_id": by_id[neighbor_id].document_id,
                    }
                    for neighbor_id in similar_ids
                    if neighbor_id in by_id
                ],
                "centrality": obj.centrality,
                "influence": obj.influence,
                "role": obj.node_role or "core",
                "pinned": bool(obj.pinned_topic),
                "is_read": bool(obj.document.is_read),
                "folder_id": obj.document.folder_id,
                "folder_name": (
                    obj.document.folder.name if obj.document.folder_id else None
                ),
                "excerpt": _excerpt(obj),
                "note_chars": _note_chars(obj),
            }
        )
    payload.update(
        {
            "data": papers,
            "papers": papers,
            "colors": collection.colors or {},
            "recommendations": collection.reading_recommendations or {},
            "topics": collection.topics or [],
            "ghosts": collection.ghost_nodes or [],
            "heatmap": collection.heatmap or {},
            "stats": collection.stats or {},
        }
    )
    return payload


def regenerate_recommendations(config: SmartCollectionConfig) -> dict[str, Any]:
    collection = models.SmartCollections.objects.first()
    if collection is None or not collection.annotation_ids:
        raise ValueError("Build a Smart Collection before generating recommendations.")
    annotations = list(
        models.Annotations.objects.filter(pk__in=collection.annotation_ids)
        .select_related("document")
        .order_by("id")
    )
    topic_map = {
        item.id: {"major": item.major_topic or "Uncategorized", "sub": item.sub_topic}
        for item in annotations
    }
    coordinates = {
        item.id: [float(item.x_coordinate or 0.0), float(item.y_coordinate or 0.0)]
        for item in annotations
    }
    ids = [item.id for item in annotations]
    recommendations, ghosts = _build_discovery(
        None,
        config,
        topic_map,
        {item.id: item for item in annotations},
        coordinates,
        ids,
        None,
        auto_import=True,
    )
    collection.reading_recommendations = recommendations
    collection.ghost_nodes = ghosts
    collection.save(
        update_fields=["reading_recommendations", "ghost_nodes", "updated_at"]
    )
    return recommendations


def build_smart_collection(
    job: models.SmartCollectionJob, config: SmartCollectionConfig
) -> models.SmartCollections:
    from .clustering import (
        compute_node_metrics,
        influence_heatmap,
        project_coordinates,
        similar_papers as neighbor_map,
    )

    job.status = models.SmartCollectionJob.Status.RUNNING
    job.stage = "preflight"
    job.progress = 1
    job.started_at = timezone.now()
    job.error_code = ""
    job.error_message = ""
    job.save(
        update_fields=[
            "status",
            "stage",
            "progress",
            "started_at",
            "error_code",
            "error_message",
            "updated_at",
        ]
    )
    annotations = list(
        models.Annotations.objects.select_related("document")
        .order_by("-updated_at")[:MAX_ANNOTATIONS]
    )
    if not annotations:
        raise ValueError(
            "Add notes or annotations to at least one paper before building a Smart Collection."
        )
    job.total_items = len(annotations)
    job.save(update_fields=["total_items", "updated_at"])

    _embed_annotations(job, annotations, config.embedding)
    _set_job(job, stage="clustering", progress=30, processed_items=len(annotations))
    ids, matrix = _vectors_for(annotations, config.embedding)
    cluster_map, cluster_method = _cluster(ids, matrix)

    _set_job(job, stage="labeling", progress=42)
    annotations_by_id = {item.id: item for item in annotations}
    samples, fallback = _representative_content(cluster_map, annotations_by_id)
    labels, generation_exhausted = _label_clusters(job, config, samples, fallback)
    topic_map: dict[int, dict[str, str | None]] = {}
    for annotation_id, cluster in cluster_map.items():
        major_number = int(cluster["major"] if cluster["major"] is not None else -1)
        sub_number = cluster["sub"]
        major_label = (
            "Uncategorized"
            if major_number < 0
            else labels.get(f"major:{major_number}", f"Research Topic {major_number + 1}")
        )
        sub_label = (
            labels.get(f"sub:{major_number}:{int(sub_number)}")
            if sub_number is not None and int(sub_number) >= 0
            else None
        )
        topic_map[annotation_id] = {
            "major": _sanitize_label(major_label, "Uncategorized"),
            "sub": _sanitize_label(sub_label, "") if sub_label else None,
        }
    _apply_pins(topic_map, annotations_by_id)

    _set_job(job, stage="projection", progress=58)
    coordinates = project_coordinates(ids, matrix)
    metrics = compute_node_metrics(ids, cluster_map, matrix)
    _set_job(job, stage="similarity", progress=70)
    neighbors = neighbor_map(ids, matrix)
    topics, stats = _topic_records(
        ids, topic_map, coordinates, metrics, annotations_by_id, matrix, cluster_method
    )
    heatmap = influence_heatmap(
        [coordinates[item][0] for item in ids],
        [coordinates[item][1] for item in ids],
        [metrics[item].influence for item in ids],
    )

    _set_job(job, stage="discovery", progress=80)
    recommendations, ghosts = _build_discovery(
        job,
        config,
        topic_map,
        annotations_by_id,
        coordinates,
        ids,
        matrix,
        auto_import=True,
        use_generation=not generation_exhausted,
    )
    stats["ghost_count"] = len(ghosts)
    stats["auto_imported"] = int((recommendations or {}).get("auto_imported") or 0)
    _check_cancelled(job)

    _set_job(job, stage="publishing", progress=92)
    updates = []
    for annotation_id in ids:
        item = annotations_by_id[annotation_id]
        item.major_topic = topic_map[annotation_id]["major"]
        item.sub_topic = topic_map[annotation_id]["sub"]
        item.x_coordinate = coordinates[annotation_id][0]
        item.y_coordinate = coordinates[annotation_id][1]
        item.similar_papers = neighbors[annotation_id]
        item.centrality = metrics[annotation_id].centrality
        item.influence = metrics[annotation_id].influence
        item.node_role = metrics[annotation_id].role
        updates.append(item)
    major_topics = [topic["name"] for topic in topics]
    colors = generate_colors(major_topics)

    with transaction.atomic():
        models.Annotations.objects.bulk_update(
            updates,
            [
                "major_topic",
                "sub_topic",
                "x_coordinate",
                "y_coordinate",
                "similar_papers",
                "centrality",
                "influence",
                "node_role",
            ],
            batch_size=500,
        )
        collection = models.SmartCollections.objects.select_for_update().first()
        if collection is None:
            collection = models.SmartCollections()
        collection.annotation_ids = ids
        collection.is_ready = True
        collection.colors = colors
        collection.reading_recommendations = recommendations
        collection.topics = topics
        collection.ghost_nodes = ghosts
        collection.heatmap = heatmap
        collection.stats = stats
        collection.source_job = job
        collection.save()

    job.status = models.SmartCollectionJob.Status.COMPLETED
    job.stage = "completed"
    job.progress = 100
    job.processed_items = len(ids)
    job.finished_at = timezone.now()
    job.save(
        update_fields=[
            "status",
            "stage",
            "progress",
            "processed_items",
            "finished_at",
            "updated_at",
        ]
    )
    return collection


def safe_failure(exc: BaseException, stage: str) -> tuple[str, str]:
    label = stage_label(stage)
    if isinstance(exc, ResearchMarkerError):
        return exc.code, exc.message[:1000]
    if isinstance(exc, SmartCollectionCancelled):
        return "cancelled", "Smart Collection generation was cancelled."
    if isinstance(exc, ValueError):
        return "invalid_smart_collection_data", str(exc)[:1000]
    if isinstance(exc, (requests.Timeout, TimeoutError)):
        return (
            "provider_timeout",
            f"Timed out during {label.lower()}: {str(exc)[:400]}",
        )
    if isinstance(exc, (requests.ConnectionError, ConnectionError, OSError)):
        return (
            "provider_unreachable",
            f"Could not reach the AI provider during {label.lower()}: {str(exc)[:400]}",
        )
    detail = str(exc).strip()[:400]
    LOGGER.exception("Unexpected Smart Collection failure during %s", stage)
    if detail:
        return (
            "smart_collection_failed",
            f"Smart Collection failed during {label.lower()}: {detail}",
        )
    return (
        "smart_collection_failed",
        f"Smart Collection generation failed during {label.lower()}. "
        "Check the backend logs and retry.",
    )
