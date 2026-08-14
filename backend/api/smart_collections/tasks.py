from __future__ import annotations

import logging

from django.utils import timezone
from api import models
from api.providers.embeddings import EmbeddingSpec
from api.task_queue import enqueue_task
from .config import SmartCollectionConfig
from .service import (
    SmartCollectionCancelled,
    build_smart_collection,
    safe_failure,
)


LOGGER = logging.getLogger(__name__)
SMART_COLLECTION_TASK_HOOK = (
    "api.smart_collections.tasks.finalize_smart_collection_task"
)


def async_task(*args, **kwargs):
    """Compatibility wrapper that also wakes the on-demand Django-Q worker."""
    return enqueue_task(*args, **kwargs)


def queue_smart_collection_job(job_id: str) -> str:
    """Queue the runner without relying on django-q's pydoc resolver.

    django-q2 accepts callables as task payloads.  Passing the callable is
    important in a PyInstaller build, where ``pydoc.locate`` can fail even
    though the module is present in the frozen archive.  Hooks remain dotted
    paths because django-q stores them in a CharField and resolves them with
    importlib/getattr instead of pydoc.
    """
    return async_task(
        run_smart_collection_job,
        str(job_id),
        hook=SMART_COLLECTION_TASK_HOOK,
        timeout=1800,
    )


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
    job.error_code = "worker_failure"
    result = getattr(task, "result", None)
    detail = str(result).strip()[:400] if result else ""
    stage = job.stage or "queued"
    if detail:
        job.error_message = (
            f"The background worker stopped during '{stage}' before the Smart "
            f"Collection finished: {detail}. Restart the django-q worker and retry."
        )
    else:
        job.error_message = (
            f"The background worker stopped during '{stage}' before the Smart "
            "Collection finished (timeout or crash). Restart the django-q worker "
            "and retry."
        )
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
