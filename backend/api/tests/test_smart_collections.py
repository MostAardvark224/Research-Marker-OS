import uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone
from django_q.models import Task
from rest_framework.test import APIClient

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


class SmartCollectionAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _annotation(self):
        document = models.Document.objects.create(
            title="Paper", file="documents/paper.pdf"
        )
        return models.Annotations.objects.create(document=document, notepad="Research note")

    def _job(self, **overrides):
        values = {
            "embedding_provider": "test-embeddings",
            "embedding_model": "embedding-model",
            "embedding_dimensions": 8,
            "generation_provider": "test-generation",
            "generation_model": "generation-model",
        }
        values.update(overrides)
        return models.SmartCollectionJob.objects.create(**values)

    def test_create_requires_at_least_one_annotation(self):
        response = self.client.post(reverse("smart-collection"), {}, format="json")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data["error"], "no_annotations")

    @patch("api.views.queue_smart_collection_job", return_value="task-123")
    @patch("api.views.get_smart_collection_config")
    def test_create_records_job_and_queues_it(self, get_config, queue):
        self._annotation()
        get_config.return_value = SimpleNamespace(
            embedding=SimpleNamespace(provider="local", model="embed", dimensions=16),
            generation_provider="gemini",
            generation_model="flash",
        )

        response = self.client.post(
            reverse("smart-collection"),
            {"embedding_provider": "local", "generation_provider": "gemini"},
            format="json",
        )

        self.assertEqual(response.status_code, 202)
        job = models.SmartCollectionJob.objects.get()
        self.assertEqual(job.task_id, "task-123")
        self.assertEqual(job.total_items, 1)
        queue.assert_called_once_with(str(job.id))

    @patch("api.views.queue_smart_collection_job", side_effect=RuntimeError("worker unavailable"))
    @patch("api.views.get_smart_collection_config")
    def test_queue_failure_marks_job_failed(self, get_config, _queue):
        self._annotation()
        get_config.return_value = SimpleNamespace(
            embedding=SimpleNamespace(provider="local", model="embed", dimensions=16),
            generation_provider="gemini",
            generation_model="flash",
        )
        response = self.client.post(reverse("smart-collection"), {}, format="json")
        self.assertEqual(response.status_code, 503)
        job = models.SmartCollectionJob.objects.get()
        self.assertEqual(job.status, models.SmartCollectionJob.Status.FAILED)
        self.assertTrue(job.error_code)

    @patch("api.views.reconcile_stale_job", side_effect=lambda job: job)
    def test_create_returns_existing_active_job(self, _reconcile):
        active = self._job(task_id="active-task")
        response = self.client.post(reverse("smart-collection"), {}, format="json")
        self.assertEqual(response.status_code, 202)
        self.assertIs(response.data["already_running"], True)
        self.assertEqual(response.data["job"]["id"], str(active.id))

    def test_get_returns_empty_contract_without_published_collection(self):
        response = self.client.get(reverse("smart-collection"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"], [])
        self.assertEqual(response.data["colors"], {})

    def test_get_serializes_ready_collection(self):
        annotation = self._annotation()
        annotation.major_topic = "Methods"
        annotation.sub_topic = "Testing"
        annotation.x_coordinate = 1.5
        annotation.y_coordinate = 2.5
        annotation.similar_papers = [{"id": 2}]
        annotation.save()
        models.SmartCollections.objects.create(
            annotation_ids=[annotation.id],
            is_ready=True,
            colors={"Methods": "#fff"},
            reading_recommendations={"next": annotation.id},
        )
        response = self.client.get(reverse("smart-collection"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"][0]["major_topic"], "Methods")
        self.assertEqual(response.data["colors"], {"Methods": "#fff"})

    @patch("api.views.reconcile_stale_job", side_effect=lambda job: job)
    def test_poll_supports_task_id_and_missing_job(self, _reconcile):
        job = self._job(task_id="task-abc", status=models.SmartCollectionJob.Status.RUNNING)
        found = self.client.get(
            reverse("poll-smart-collection", kwargs={"task_id": "task-abc"})
        )
        missing = self.client.get(
            reverse("poll-smart-collection", kwargs={"task_id": "unknown"})
        )
        self.assertEqual(found.status_code, 200)
        self.assertEqual(found.data["state"], "running")
        self.assertEqual(found.data["job"]["id"], str(job.id))
        self.assertEqual(missing.status_code, 404)

    def test_poll_null_is_a_no_task_state(self):
        response = self.client.get(
            reverse("poll-smart-collection", kwargs={"task_id": "null"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["state"], "no_task")

    @patch("api.views.reconcile_stale_job", side_effect=lambda job: job)
    def test_job_detail_and_cancel(self, _reconcile):
        job = self._job()
        detail_url = reverse("smart-collection-job", kwargs={"job_id": job.id})
        detail = self.client.get(detail_url)
        cancelled = self.client.delete(detail_url)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(cancelled.status_code, 202)
        job.refresh_from_db()
        self.assertIs(job.cancel_requested, True)

    def test_unknown_job_returns_404(self):
        response = self.client.get(
            reverse("smart-collection-job", kwargs={"job_id": uuid.uuid4()})
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["error"], "job_not_found")

    def test_reading_recommendations_empty_and_populated(self):
        empty = self.client.get(reverse("reading-recommendations"))
        models.SmartCollections.objects.create(
            is_ready=True, reading_recommendations={"next": [1, 2]}
        )
        populated = self.client.get(reverse("reading-recommendations"))
        self.assertEqual(empty.data["recommendations"], {})
        self.assertEqual(populated.data["recommendations"], {"next": [1, 2]})

    @patch("api.views.get_smart_collection_config", return_value=SimpleNamespace())
    @patch("api.views.regenerate_recommendations", return_value={"next": [3]})
    def test_regenerate_recommendations(self, regenerate, _config):
        response = self.client.post(reverse("reading-recommendations"), {}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["recommendations"], {"next": [3]})
        regenerate.assert_called_once()
