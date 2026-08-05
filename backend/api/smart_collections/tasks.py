from __future__ import annotations

import logging

from django.utils import timezone

from api import models
from api.providers.embeddings import EmbeddingSpec
from .config import SmartCollectionConfig
from .service import (
    SmartCollectionCancelled,
    build_smart_collection,
    safe_failure,
)


LOGGER = logging.getLogger(__name__)


def run_smart_collection_job(job_id: str) -> None:
    job = models.SmartCollectionJob.objects.get(pk=job_id)
    config = SmartCollectionConfig(
        embedding=EmbeddingSpec(
            provider=job.embedding_provider,
            model=job.embedding_model,
            dimensions=job.embedding_dimensions,
        ),
        generation_provider=job.generation_provider,
        generation_model=job.generation_model,
    )
    try:
        build_smart_collection(job, config)
    except SmartCollectionCancelled:
        job.refresh_from_db()
        job.status = models.SmartCollectionJob.Status.CANCELLED
        job.stage = "cancelled"
        job.error_code = ""
        job.error_message = ""
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
    except BaseException as exc:
        job.refresh_from_db()
        code, message = safe_failure(exc, job.stage)
        job.status = models.SmartCollectionJob.Status.FAILED
        job.stage = "failed"
        job.error_code = code
        job.error_message = message
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
        raise


def finalize_smart_collection_task(task) -> None:
    """Record worker-level failures such as hard django-q timeouts."""
    if getattr(task, "success", False):
        return
    args = getattr(task, "args", None) or []
    if not args:
        return
    try:
        job = models.SmartCollectionJob.objects.get(pk=str(args[0]))
    except (models.SmartCollectionJob.DoesNotExist, ValueError, TypeError):
        return
    if job.status not in (
        models.SmartCollectionJob.Status.QUEUED,
        models.SmartCollectionJob.Status.RUNNING,
    ):
        return
    job.status = models.SmartCollectionJob.Status.FAILED
    job.stage = "failed"
    job.error_code = "worker_failure"
    job.error_message = (
        "The background worker stopped before the Smart Collection finished. "
        "Restart the worker and retry."
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
