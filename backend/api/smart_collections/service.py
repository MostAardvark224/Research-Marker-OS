from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
import json
import logging
import re
from typing import Any

from django.db import transaction
from django.utils import timezone
import hdbscan
import numpy as np
import requests
import umap
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
MAX_SIMILAR_PAPERS = 6
SIMILARITY_THRESHOLD = 0.55
STALE_JOB_AFTER = timedelta(minutes=35)
LABEL_MAX_LENGTH = 100


class SmartCollectionCancelled(Exception):
    pass


def serialize_job(job: models.SmartCollectionJob) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "task_id": job.task_id,
        "status": job.status,
        "stage": job.stage,
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


def reconcile_stale_job(job: models.SmartCollectionJob) -> models.SmartCollectionJob:
    if (
        job.status
        in (
            models.SmartCollectionJob.Status.QUEUED,
            models.SmartCollectionJob.Status.RUNNING,
        )
        and job.updated_at < timezone.now() - STALE_JOB_AFTER
    ):
        job.status = models.SmartCollectionJob.Status.FAILED
        job.stage = "failed"
        job.error_code = "worker_timeout"
        job.error_message = (
            "The Smart Collection worker stopped responding. Restart the background "
            "worker and retry."
        )
        job.finished_at = timezone.now()
        job.save(
            update_fields=[
                "status",
                "stage",
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


def _annotation_text(annotation: models.Annotations) -> str:
    sticky_parts: list[str] = []
    data = annotation.sticky_note_data
    if isinstance(data, list):
        sticky_parts = [
            str(item.get("content", "")).strip()
            for item in data
            if isinstance(item, dict) and str(item.get("content", "")).strip()
        ]
    elif isinstance(data, dict):
        sticky_parts = [
            str(item.get("content", "")).strip()
            for item in data.values()
            if isinstance(item, dict) and str(item.get("content", "")).strip()
        ]
    return "\n".join(
        part
        for part in [
            f"Document: {annotation.document.title}",
            "Sticky notes: " + "\n".join(sticky_parts) if sticky_parts else "",
            "Notepad: " + str(annotation.notepad or "").strip()
            if annotation.notepad
            else "",
        ]
        if part
    )[:12_000]


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
        _check_cancelled(job)
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


def _cluster(ids: list[int], matrix: np.ndarray) -> dict[int, dict[str, int | None]]:
    count = len(ids)
    if count < 4:
        return {
            annotation_id: {"major": 0, "sub": None}
            for annotation_id in ids
        }

    min_cluster_size = min(count, max(4, count // 10))
    labels = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min(4, min_cluster_size),
        metric="euclidean",
    ).fit_predict(matrix)
    result = {
        annotation_id: {"major": int(labels[index]), "sub": None}
        for index, annotation_id in enumerate(ids)
    }
    major_indices: dict[int, list[int]] = defaultdict(list)
    for index, label in enumerate(labels):
        if int(label) >= 0:
            major_indices[int(label)].append(index)

    for major, indices in sorted(major_indices.items()):
        if len(indices) < 4:
            continue
        sub_matrix = matrix[indices]
        sub_min = min(len(indices), max(2, len(indices) // 10))
        sub_labels = hdbscan.HDBSCAN(
            min_cluster_size=sub_min,
            min_samples=sub_min,
            metric="euclidean",
        ).fit_predict(sub_matrix)
        for relative_index, sub_label in enumerate(sub_labels):
            result[ids[indices[relative_index]]]["sub"] = int(sub_label)
    return result


def _representative_content(
    cluster_map: dict[int, dict[str, int | None]],
    annotations_by_id: dict[int, models.Annotations],
) -> tuple[dict[str, list[str]], dict[str, str]]:
    samples: dict[str, list[str]] = defaultdict(list)
    fallback: dict[str, str] = {}
    for annotation_id in sorted(cluster_map):
        labels = cluster_map[annotation_id]
        major = int(labels["major"])
        if major >= 0:
            key = f"major:{major}"
            fallback[key] = f"Research Topic {major + 1}"
            if len(samples[key]) < 4:
                samples[key].append(_annotation_text(annotations_by_id[annotation_id])[:1500])
        sub = labels["sub"]
        if major >= 0 and sub is not None and int(sub) >= 0:
            key = f"sub:{major}:{int(sub)}"
            fallback[key] = f"Subtopic {int(sub) + 1}"
            if len(samples[key]) < 3:
                samples[key].append(_annotation_text(annotations_by_id[annotation_id])[:1200])
    return dict(samples), fallback


def _retryable_generation_error(exc: BaseException) -> bool:
    from api.errors import ProviderRateLimited

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
        wait=wait_random_exponential(multiplier=1, max=15),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    if config.generation_provider == "codex":
        from api.providers.codex import get_codex_provider

        return retryer(
            get_codex_provider().generate_text,
            prompt,
            system_prompt=system_prompt,
            model=config.generation_model,
        )

    env = load_env_vars()
    return retryer(
        send_prompt,
        provider=config.generation_provider,
        api_key=get_provider_api_key(config.generation_provider, env),
        model=config.generation_model,
        prompt=prompt,
        system_prompt=system_prompt,
        temperature=0.2,
        base_url=get_provider_base_url(config.generation_provider, env),
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


def _label_clusters(
    job: models.SmartCollectionJob,
    config: SmartCollectionConfig,
    samples: dict[str, list[str]],
    fallback: dict[str, str],
) -> dict[str, str]:
    if not samples:
        return fallback
    prompt = (
        "Label every cluster in the following JSON. Return one JSON object whose keys "
        "exactly match the input keys and whose values are concise 2-5 word academic "
        "topic labels. Return JSON only.\n\n"
        + json.dumps(samples, ensure_ascii=False)
    )
    try:
        generated = _json_object(
            _generate(
                config,
                prompt,
                "You label groups of research notes. Return valid JSON only.",
            )
        )
        return {
            key: _sanitize_label(generated.get(key), fallback[key])
            for key in fallback
        }
    except Exception as exc:
        LOGGER.warning("Smart Collection label generation failed: %s", exc)
        _set_job(
            job,
            stage="labeling",
            progress=48,
            warning=(
                "AI topic labels were unavailable, so deterministic fallback labels were used."
            ),
        )
        return fallback


def _coordinates(ids: list[int], matrix: np.ndarray) -> dict[int, list[float]]:
    count = len(ids)
    if count == 1:
        return {ids[0]: [0.0, 0.0]}
    if count == 2:
        return {ids[0]: [-1.0, 0.0], ids[1]: [1.0, 0.0]}
    reducer = umap.UMAP(
        n_components=2,
        n_neighbors=max(2, min(15, count - 1)),
        metric="cosine",
        min_dist=0.1,
        random_state=42,
        n_jobs=1,
    )
    result = reducer.fit_transform(matrix)
    return {
        annotation_id: [float(result[index][0]), float(result[index][1])]
        for index, annotation_id in enumerate(ids)
    }


def _similar_papers(ids: list[int], matrix: np.ndarray) -> dict[int, list[int]]:
    similarities = matrix @ matrix.T
    output: dict[int, list[int]] = {}
    for index, annotation_id in enumerate(ids):
        ranked = np.argsort(similarities[index])[::-1]
        neighbors = [
            ids[int(candidate)]
            for candidate in ranked
            if int(candidate) != index
            and float(similarities[index, candidate]) >= SIMILARITY_THRESHOLD
        ][:MAX_SIMILAR_PAPERS]
        output[annotation_id] = neighbors
    return output


def _recommendations(
    job: models.SmartCollectionJob,
    config: SmartCollectionConfig,
    topics: dict[int, dict[str, str | None]],
    annotations_by_id: dict[int, models.Annotations],
) -> dict[str, Any] | None:
    context: dict[str, list[str]] = defaultdict(list)
    for annotation_id in sorted(topics):
        major = str(topics[annotation_id]["major"])
        titles = context[major]
        title = annotations_by_id[annotation_id].document.title
        if title not in titles and len(titles) < 6:
            titles.append(title)
    prompt = (
        "Based on this research-topic map, recommend at most five adjacent research "
        "areas. Return a JSON object keyed by topic; each value must contain overview, "
        "paper1, and paper2 strings. Return JSON only.\n\n"
        + json.dumps(context, ensure_ascii=False)
    )
    try:
        return _json_object(
            _generate(
                config,
                prompt,
                "You are an academic research advisor. Return valid JSON only.",
            )
        )
    except Exception as exc:
        LOGGER.warning("Smart Collection recommendations failed: %s", exc)
        _set_job(
            job,
            stage="recommendations",
            progress=82,
            warning="Reading recommendations could not be generated. The graph is still complete.",
        )
        return None


def regenerate_recommendations(config: SmartCollectionConfig) -> dict[str, Any]:
    collection = models.SmartCollections.objects.first()
    if collection is None or not collection.annotation_ids:
        raise ValueError("Build a Smart Collection before generating recommendations.")
    annotations = list(
        models.Annotations.objects.filter(pk__in=collection.annotation_ids)
        .select_related("document")
        .order_by("id")
    )
    context: dict[str, list[str]] = defaultdict(list)
    for annotation in annotations:
        topic = annotation.major_topic or "Uncategorized"
        if (
            annotation.document.title not in context[topic]
            and len(context[topic]) < 6
        ):
            context[topic].append(annotation.document.title)
    prompt = (
        "Based on this research-topic map, recommend at most five adjacent research "
        "areas. Return a JSON object keyed by topic; each value must contain overview, "
        "paper1, and paper2 strings. Return JSON only.\n\n"
        + json.dumps(context, ensure_ascii=False)
    )
    recommendations = _json_object(
        _generate(
            config,
            prompt,
            "You are an academic research advisor. Return valid JSON only.",
        )
    )
    collection.reading_recommendations = recommendations
    collection.save(update_fields=["reading_recommendations", "updated_at"])
    return recommendations


def build_smart_collection(
    job: models.SmartCollectionJob, config: SmartCollectionConfig
) -> models.SmartCollections:
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
    cluster_map = _cluster(ids, matrix)

    _set_job(job, stage="labeling", progress=42)
    annotations_by_id = {item.id: item for item in annotations}
    samples, fallback = _representative_content(cluster_map, annotations_by_id)
    labels = _label_clusters(job, config, samples, fallback)
    topic_map: dict[int, dict[str, str | None]] = {}
    for annotation_id, cluster in cluster_map.items():
        major_number = int(cluster["major"])
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

    _set_job(job, stage="projection", progress=58)
    coordinates = _coordinates(ids, matrix)
    _set_job(job, stage="similarity", progress=70)
    neighbors = _similar_papers(ids, matrix)
    _set_job(job, stage="recommendations", progress=80)
    recommendations = _recommendations(job, config, topic_map, annotations_by_id)
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
        updates.append(item)
    major_topics = sorted({str(topic_map[item]["major"]) for item in ids})
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
    if isinstance(exc, ResearchMarkerError):
        return exc.code, exc.message[:1000]
    if isinstance(exc, SmartCollectionCancelled):
        return "cancelled", "Smart Collection generation was cancelled."
    if isinstance(exc, ValueError):
        return "invalid_smart_collection_data", str(exc)[:1000]
    LOGGER.exception("Unexpected Smart Collection failure during %s", stage)
    return (
        "smart_collection_failed",
        f"Smart Collection generation failed during {stage}. Check the backend logs and retry.",
    )
