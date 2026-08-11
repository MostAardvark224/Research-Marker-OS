import uuid
from datetime import timedelta
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from django_q.models import Task

from api import models
from api.smart_collections.service import QUEUED_STALE_AFTER, reconcile_stale_job
from api.smart_collections.tasks import (
    SMART_COLLECTION_TASK_HOOK,
    queue_smart_collection_job,
    run_smart_collection_job,
)


class SmartCollectionQueueTests(SimpleTestCase):
    @patch("api.smart_collections.tasks.async_task", return_value="task-id")
    def test_queue_uses_callable_to_bypass_django_q_pydoc(self, async_task):
        job_id = uuid.uuid4()

        result = queue_smart_collection_job(str(job_id))

        self.assertEqual(result, "task-id")
        async_task.assert_called_once_with(
            run_smart_collection_job,
            str(job_id),
            hook=SMART_COLLECTION_TASK_HOOK,
            timeout=1800,
        )


class SmartCollectionReconciliationTests(TestCase):
    def _job(self, **overrides):
        values = {
            "embedding_provider": "test-embeddings",
            "embedding_model": "test-embedding-model",
            "embedding_dimensions": 8,
            "generation_provider": "test-generation",
            "generation_model": "test-generation-model",
        }
        values.update(overrides)
        return models.SmartCollectionJob.objects.create(**values)

    def _failed_task(self, job, detail):
        now = timezone.now()
        return Task.objects.create(
            id=job.task_id,
            name="smart-collection-test",
            func="api.smart_collections.tasks.run_smart_collection_job",
            args=(str(job.id),),
            kwargs={},
            started=now,
            stopped=now,
            result=detail,
            success=False,
        )

    def test_recorded_worker_failure_is_reported_immediately(self):
        task_id = "a" * 32
        job = self._job(task_id=task_id)
        detail = (
            "Function api.smart_collections.tasks.run_smart_collection_job "
            "is not defined"
        )
        self._failed_task(job, detail)

        reconciled = reconcile_stale_job(job)

        self.assertEqual(reconciled.status, models.SmartCollectionJob.Status.FAILED)
        self.assertEqual(reconciled.error_code, "worker_failure")
        self.assertIn(detail, reconciled.error_message)
        self.assertNotIn("worker_not_running", reconciled.error_message)

    def test_misclassified_worker_not_running_failure_is_repaired(self):
        job = self._job(
            task_id="c" * 32,
            status=models.SmartCollectionJob.Status.FAILED,
            error_code="worker_not_running",
            error_message="The background worker is probably not running.",
            finished_at=timezone.now(),
        )
        detail = (
            "Function api.smart_collections.tasks.run_smart_collection_job "
            "is not defined"
        )
        self._failed_task(job, detail)

        reconciled = reconcile_stale_job(job)

        self.assertEqual(reconciled.error_code, "worker_failure")
        self.assertIn(detail, reconciled.error_message)

    def test_stale_queue_without_task_failure_reports_worker_not_running(self):
        job = self._job(task_id="b" * 32)
        models.SmartCollectionJob.objects.filter(pk=job.pk).update(
            updated_at=timezone.now() - QUEUED_STALE_AFTER - timedelta(seconds=1)
        )
        job.refresh_from_db()

        reconciled = reconcile_stale_job(job)

        self.assertEqual(reconciled.status, models.SmartCollectionJob.Status.FAILED)
        self.assertEqual(reconciled.error_code, "worker_not_running")
