from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from api.models import Document, Folder
from api.scholar_inbox import ScholarInboxError


class ArxivAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_metadata_rejects_invalid_arxiv_value(self):
        response = self.client.post(
            reverse("arxiv-paper-metadata"), {"arxiv_url": "not arxiv"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    @patch("api.views.fetch_arxiv_metadata")
    def test_metadata_maps_upstream_failure_to_bad_gateway(self, fetch):
        fetch.side_effect = RuntimeError("network down")
        response = self.client.post(
            reverse("arxiv-paper-metadata"), {"arxiv_id": "2401.12345"}, format="json"
        )
        self.assertEqual(response.status_code, 502)

    @patch("api.views.fetch_arxiv_metadata")
    def test_metadata_returns_upstream_record(self, fetch):
        fetch.return_value = {"id": "2401.12345", "title": "Test", "pdf_url": "https://x/pdf"}
        response = self.client.post(
            reverse("arxiv-paper-metadata"), {"arxiv_id": "2401.12345"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["title"], "Test")

    @patch("api.views._apply_ocr_settings_to_document")
    @patch("api.views._stream_pdf_to_document")
    @patch("api.views.fetch_arxiv_metadata")
    def test_import_creates_document_with_selected_title_and_folder(self, fetch, stream, apply_ocr):
        folder = Folder.objects.create(name="Imports")
        fetch.return_value = {"title": "arXiv title", "pdf_url": "https://x/paper.pdf"}
        document = Document.objects.create(title="Custom", file="documents/custom.pdf", folder=folder)
        stream.return_value = document

        response = self.client.post(
            reverse("import-arxiv-paper"),
            {
                "arxiv_id": "2401.12345",
                "title": "Custom",
                "folder_id": folder.id,
                "skip_ocr": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        stream.assert_called_once_with("https://x/paper.pdf", "Custom", folder)
        apply_ocr.assert_called_once_with(document, True, "paddleocr")

    @patch("api.views.fetch_arxiv_metadata")
    def test_import_rejects_unknown_folder(self, fetch):
        fetch.return_value = {"title": "Paper", "pdf_url": "https://x/paper.pdf"}
        response = self.client.post(
            reverse("import-arxiv-paper"),
            {"arxiv_id": "2401.12345", "folder_id": 999999},
            format="json",
        )
        self.assertEqual(response.status_code, 400)


class OCRAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_unknown_document_returns_404(self):
        response = self.client.post(reverse("document-ocr", kwargs={"pk": 999999}), {}, format="json")
        self.assertEqual(response.status_code, 404)

    def test_already_running_ocr_returns_conflict(self):
        document = Document.objects.create(
            title="Scan", file="documents/scan.pdf", ocr_status=Document.OcrStatus.PROCESSING
        )
        response = self.client.post(
            reverse("document-ocr", kwargs={"pk": document.id}), {}, format="json"
        )
        self.assertEqual(response.status_code, 409)

    @patch("api.views.async_task")
    @patch("api.views.get_ocr_providers")
    def test_valid_ocr_request_queues_background_job(self, providers, async_task):
        providers.return_value = [
            {"id": "paddleocr", "label": "PaddleOCR", "kind": "local", "has_api_key": False}
        ]
        document = Document.objects.create(title="Scan", file="documents/scan.pdf")

        response = self.client.post(
            reverse("document-ocr", kwargs={"pk": document.id}),
            {"ocr_provider": "paddleocr", "model": "model-a"},
            format="json",
        )

        self.assertEqual(response.status_code, 202)
        document.refresh_from_db()
        self.assertEqual(document.ocr_status, Document.OcrStatus.QUEUED)
        async_task.assert_called_once_with(
            "api.OCR.create_searchable_document_pdf", document.id, "paddleocr", "model-a"
        )


class ScholarInboxAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    @patch("api.views.import_scholar_inbox_papers")
    def test_success_response_has_stable_summary(self, importer):
        importer.return_value = {
            "message": "Done", "imported": 2, "skipped": 1, "unmatched": 3,
            "digest_found": True, "titles_found": 5,
        }
        response = self.client.post(
            reverse("fetch-scholar-inbox-papers"), {"amount_to_import": "2"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["imported"], 2)
        importer.assert_called_once_with("2", skip_ocr=True, ocr_provider="paddleocr")

    @patch("api.views.import_scholar_inbox_papers")
    def test_actionable_import_error_preserves_code_and_status(self, importer):
        importer.side_effect = ScholarInboxError(
            "Credentials missing", code="credentials_missing", http_status=400
        )
        response = self.client.post(reverse("fetch-scholar-inbox-papers"), {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "credentials_missing")
        self.assertEqual(response.data["imported"], 0)
