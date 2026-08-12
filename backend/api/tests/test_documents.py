import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from api.models import Document, Folder


class DocumentAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.media = tempfile.TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.media.name)
        self.media_override.enable()

    def tearDown(self):
        self.media_override.disable()
        self.media.cleanup()

    def make_document(self, title="Paper", folder=None, **values):
        defaults = {"title": title, "file": f"documents/{title}.pdf", "folder": folder}
        defaults.update(values)
        return Document.objects.create(**defaults)

    def test_list_and_complete_fetch_group_documents(self):
        folder = Folder.objects.create(name="Research")
        assigned = self.make_document("Assigned", folder)
        unassigned = self.make_document("Loose")

        listing = self.client.get(reverse("documents-list"))
        complete = self.client.get(reverse("complete-fetch"))

        self.assertEqual(listing.status_code, 200)
        self.assertEqual({item["id"] for item in listing.data}, {assigned.id, unassigned.id})
        self.assertEqual(complete.status_code, 200)
        self.assertEqual(complete.data["folders"][0]["documents"][0]["id"], assigned.id)
        self.assertEqual(complete.data["Unassigned"][0]["id"], unassigned.id)

    @patch("api.views._queue_context_ingestion")
    def test_multipart_upload_skipping_ocr_queues_context(self, queue_context):
        upload = SimpleUploadedFile("example.pdf", b"%PDF-1.4\ntest", "application/pdf")

        response = self.client.post(
            reverse("documents-list"),
            {"file": upload, "skip_ocr": "true", "ocr_provider": "paddleocr"},
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        document = Document.objects.get()
        self.assertEqual(document.title, "example")
        self.assertEqual(document.ocr_status, Document.OcrStatus.NOT_STARTED)
        self.assertTrue(Path(document.file.path).is_file())
        queue_context.assert_called_once_with(document)

    @patch("api.views.async_task")
    @patch("api.views.get_ocr_providers")
    def test_upload_with_ocr_records_state_and_queues_job(self, providers, async_task):
        providers.return_value = [
            {"id": "paddleocr", "label": "PaddleOCR", "kind": "local", "has_api_key": False}
        ]
        upload = SimpleUploadedFile("scan.pdf", b"%PDF-1.4\nscan", "application/pdf")

        response = self.client.post(
            reverse("documents-list"),
            {"file": upload, "skip_ocr": "false", "ocr_provider": "paddleocr"},
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        document = Document.objects.get()
        self.assertEqual(document.ocr_status, Document.OcrStatus.QUEUED)
        self.assertEqual(document.context_status, "waiting_for_ocr")
        async_task.assert_called_once_with(
            "api.OCR.create_searchable_document_pdf", document.id, "paddleocr"
        )

    @patch("api.views.get_ocr_providers")
    def test_upload_rejects_unconfigured_byok_ocr(self, providers):
        providers.return_value = [
            {"id": "mistral", "label": "Mistral OCR", "kind": "byok", "has_api_key": False}
        ]
        upload = SimpleUploadedFile("scan.pdf", b"pdf", "application/pdf")

        response = self.client.post(
            reverse("documents-list"),
            {"file": upload, "skip_ocr": "false", "ocr_provider": "mistral"},
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("not configured", response.data["error"])
        self.assertFalse(Document.objects.exists())

    def test_document_is_unread_by_default_and_can_be_marked_read(self):
        document = self.make_document("Unread")

        response = self.client.get(reverse("documents-detail", kwargs={"pk": document.id}))
        self.assertEqual(response.status_code, 200)
        self.assertIs(response.data["is_read"], False)

        response = self.client.patch(
            reverse("documents-detail", kwargs={"pk": document.id}),
            {"is_read": True},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        document.refresh_from_db()
        self.assertIs(document.is_read, True)

    def test_moving_document_assigns_next_sort_order(self):
        folder = Folder.objects.create(name="Destination")
        self.make_document("Existing", folder, sort_order=3)
        moving = self.make_document("Moving", sort_order=9)

        response = self.client.patch(
            reverse("documents-detail", kwargs={"pk": moving.id}),
            {"folder": folder.id},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        moving.refresh_from_db()
        self.assertEqual(moving.folder, folder)
        self.assertEqual(moving.sort_order, 4)

    def test_delete_removes_database_row_and_physical_file(self):
        upload = SimpleUploadedFile("delete-me.pdf", b"pdf", "application/pdf")
        document = Document.objects.create(title="Delete me", file=upload)
        path = Path(document.file.path)
        self.assertTrue(path.exists())

        response = self.client.delete(reverse("documents-detail", kwargs={"pk": document.id}))

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Document.objects.filter(pk=document.id).exists())
        self.assertFalse(path.exists())

    def test_get_paper_returns_404_for_unknown_document(self):
        response = self.client.get(reverse("get-paper", kwargs={"pk": 999999}))
        self.assertEqual(response.status_code, 404)

    def test_get_paper_streams_pdf_inline(self):
        upload = SimpleUploadedFile("paper.pdf", b"%PDF-1.4\ncontent", "application/pdf")
        document = Document.objects.create(
            title="Readable Paper", file=upload, context_status="ready"
        )

        response = self.client.get(reverse("get-paper", kwargs={"pk": document.id}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("inline", response["Content-Disposition"])
        self.assertEqual(b"".join(response.streaming_content), b"%PDF-1.4\ncontent")

    def test_unknown_document_detail_returns_404(self):
        response = self.client.get(reverse("documents-detail", kwargs={"pk": 999999}))
        self.assertEqual(response.status_code, 404)
