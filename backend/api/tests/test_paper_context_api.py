from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from api.models import Document
from api.paper_context.types import PageContext, PaperContext
from api.paper_context.retrieval import ActiveReaderState


class PaperContextAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.document = Document.objects.create(
            title="Paper",
            file="documents/paper.pdf",
            document_hash="hash",
            page_count=3,
            context_status="ready",
        )

    def test_status_and_missing_document(self):
        found = self.client.get(
            reverse("paper-context-status", kwargs={"document_id": self.document.id})
        )
        missing = self.client.get(
            reverse("paper-context-status", kwargs={"document_id": 999999})
        )
        self.assertEqual(found.status_code, 200)
        self.assertEqual(found.data["page_count"], 3)
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.data["error"], "document_not_found")

    def test_reingestion_waits_for_ocr(self):
        self.document.ocr_status = Document.OcrStatus.PROCESSING
        self.document.save(update_fields=["ocr_status"])
        response = self.client.post(
            reverse("paper-context-status", kwargs={"document_id": self.document.id}),
            {"force": True},
            format="json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"], "ocr_in_progress")

    @patch("api.codex_views.async_task")
    def test_reingestion_queues_background_job(self, async_task):
        response = self.client.post(
            reverse("paper-context-status", kwargs={"document_id": self.document.id}),
            {"force": True},
            format="json",
        )
        self.assertEqual(response.status_code, 202)
        self.document.refresh_from_db()
        self.assertEqual(self.document.context_status, "queued")
        async_task.assert_called_once_with(
            "api.paper_context.ingestion.ingest_document", self.document.id, force=True
        )

    @patch("api.codex_views.get_page")
    def test_page_response_hides_local_image_path(self, get_page):
        get_page.return_value = PageContext(
            document_id=self.document.id,
            document_hash="hash",
            document_title="Paper",
            page_number=1,
            text="Page text",
            text_blocks=[],
            source_type="embedded",
            ocr_used=False,
            ocr_confidence=None,
            visually_complex=False,
            image_path="/private/page.png",
        )
        response = self.client.get(
            reverse(
                "paper-context-page",
                kwargs={"document_id": self.document.id, "page_number": 1},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("image_path", response.data)
        self.assertIs(response.data["has_image"], True)

    @patch("api.codex_views.build_paper_context")
    def test_preview_hides_local_paths(self, build):
        build.return_value = PaperContext(
            document_id=self.document.id,
            document_title="Paper",
            user_question="Explain",
            page_images=["/private/page.png"],
        )
        response = self.client.post(
            reverse("paper-context-preview", kwargs={"document_id": self.document.id}),
            {"question": "Explain"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["page_images"], ["page.png"])

    @patch("api.codex_views.update_active_context")
    def test_active_context_update_does_not_return_selected_text(self, update):
        update.return_value = ActiveReaderState(
            document_id=self.document.id,
            document_title="Paper",
            current_page=2,
            selected_text="private selection",
            selected_text_page=2,
            last_updated="now",
        )
        response = self.client.post(
            reverse("paper-context-active"),
            {
                "document_id": self.document.id,
                "document_title": "Paper",
                "current_page": 2,
                "selected_text": "private selection",
                "selected_text_page": 2,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("selected_text", response.data)

    @patch("api.paper_context.retrieval.get_active_document")
    @patch("api.paper_context.retrieval.get_active_context")
    def test_active_context_get_exposes_selection_presence_not_contents(self, get_state, get_document):
        get_state.return_value = ActiveReaderState(
            document_id=self.document.id,
            document_title="Paper",
            current_page=2,
            selected_text="private selection",
            selected_text_page=2,
            last_updated="now",
        )
        get_document.return_value = {
            "document_id": self.document.id,
            "document_title": "Paper",
            "page_count": 3,
        }
        response = self.client.get(reverse("paper-context-active"))
        self.assertEqual(response.status_code, 200)
        self.assertIs(response.data["has_selection"], True)
        self.assertNotIn("selected_text", response.data)

    @patch("api.codex_views.clear_paper_context", return_value={"documents_cleared": 2})
    def test_clear_context_forwards_ai_session_option(self, clear):
        response = self.client.post(
            reverse("paper-context-clear"), {"include_ai_sessions": False}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        clear.assert_called_once_with(include_ai_sessions=False)
