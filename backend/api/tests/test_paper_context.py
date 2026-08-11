from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile
from unittest.mock import patch

import fitz
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from api import models
from api.errors import ContextLimitExceeded, PageExtractionFailed, PageOutOfRange
from api.paper_context.builder import build_paper_context
from api.paper_context.citations import extract_citations
from api.paper_context.ingestion import clear_paper_context, ingest_document
from api.paper_context.mentions import InvalidMentionSyntax, parse_mentions
from api.paper_context.retrieval import search_document
from api.paper_context.types import ContextLimits, PageContext, PaperContext
from api.providers.codex import CodexProvider, READ_ONLY_SANDBOX_POLICY


def build_pdf_bytes() -> bytes:
    pdf = fitz.open()

    native = pdf.new_page()
    native.insert_text((50, 30), "REPEATED PAPER HEADER")
    native.insert_text((50, 90), "1 Introduction")
    native.insert_textbox(
        fitz.Rect(50, 110, 540, 350),
        "This paper proposes a deterministic paper context engine. "
        "The evaluation reports reproducible retrieval results and page citations.",
    )

    multicolumn = pdf.new_page()
    multicolumn.insert_text((50, 30), "REPEATED PAPER HEADER")
    multicolumn.insert_textbox(
        fitz.Rect(40, 80, 280, 650),
        "2 Method\nLeft-column text discusses retrieval and OCR confidence. " * 8,
    )
    multicolumn.insert_textbox(
        fitz.Rect(320, 80, 560, 650),
        "Right-column text discusses context limits and citations. " * 8,
    )

    visual = pdf.new_page()
    visual.insert_text((50, 30), "REPEATED PAPER HEADER")
    visual.draw_rect(fitz.Rect(80, 120, 500, 400), color=(0, 0, 0))
    visual.insert_text((90, 430), "Figure 1. Accuracy increases with retrieved evidence.")
    visual.insert_text((90, 480), "Equation 1: y = mx + b and ∑ x_i")

    rotated = pdf.new_page(width=595, height=842)
    rotated.insert_text((50, 30), "REPEATED PAPER HEADER")
    rotated.set_rotation(90)
    rotated.insert_text((50, 100), "Rotated appendix with readable text.")

    scanned = pdf.new_page()
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 300, 200), 0)
    pix.clear_with(245)
    scanned.insert_image(scanned.rect, pixmap=pix)

    output = pdf.tobytes()
    pdf.close()
    return output


class MentionParserTests(TestCase):
    def test_bare_single_range_list_and_order(self):
        result = parse_mentions(
            "Compare @page 4 with @pages 2, 6-7 and @page.",
            page_count=10,
            current_page=3,
        )
        self.assertEqual(result.page_numbers, [4, 2, 6, 7, 3])
        self.assertEqual(result.normalized_question, "Compare with and .")

    def test_selection_and_current_are_typed(self):
        result = parse_mentions(
            "Explain @selection using @current",
            page_count=8,
            current_page=2,
        )
        self.assertTrue(result.uses_selection)
        self.assertTrue(result.uses_current)
        self.assertEqual(result.normalized_question, "Explain using")

    def test_invalid_pages_are_rejected_without_clamping(self):
        with self.assertRaises(PageOutOfRange):
            parse_mentions("@page 0 explain", page_count=4, current_page=1)
        with self.assertRaises(InvalidMentionSyntax):
            parse_mentions("@pages 4-2 explain", page_count=4, current_page=1)

    def test_explicit_page_limit(self):
        with self.assertRaises(ContextLimitExceeded):
            parse_mentions(
                "Review @pages 1-5",
                page_count=5,
                current_page=1,
                limits=ContextLimits(maximum_explicit_pages=3),
            )


class CitationTests(TestCase):
    def test_only_supplied_page_citations_are_valid(self):
        citations = extract_citations(
            "Supported claim [p. 2]. Unsupported claim [pp. 4–5].",
            document_id=7,
            allowed_pages={2, 4},
        )
        self.assertTrue(citations[0].valid)
        self.assertFalse(citations[1].valid)


class IngestionTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.override = override_settings(MEDIA_ROOT=self.temp.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.document = models.Document.objects.create(
            title="Fixture Paper",
            file=SimpleUploadedFile(
                "fixture.pdf",
                build_pdf_bytes(),
                content_type="application/pdf",
            ),
        )

    @patch("api.paper_context.ingestion.get_app_data_dir")
    def test_native_multicolumn_figure_rotated_and_scanned_ingestion(self, app_data):
        app_data.return_value = Path(self.temp.name)
        result = ingest_document(self.document.id, allow_ocr=False)
        self.assertEqual(result, "success")
        self.document.refresh_from_db()
        self.assertEqual(self.document.page_count, 5)
        self.assertEqual(self.document.context_status, "ready")
        self.assertNotIn(
            "REPEATED PAPER HEADER",
            self.document.context_pages.get(page_number=1).extracted_text,
        )
        self.assertTrue(self.document.context_pages.get(page_number=2).visually_complex)
        self.assertTrue(self.document.context_pages.get(page_number=3).visually_complex)
        self.assertEqual(self.document.context_pages.get(page_number=4).rotation, 90)
        self.assertTrue(
            Path(self.document.context_pages.get(page_number=5).page_image_path).is_file()
        )
        self.assertTrue(search_document(self.document.id, "retrieval results"))
        self.assertEqual(ingest_document(self.document.id, allow_ocr=False), "cached")

    @patch("api.paper_context.ingestion.get_app_data_dir")
    def test_corrupt_pdf_records_failure(self, app_data):
        app_data.return_value = Path(self.temp.name)
        corrupt = models.Document.objects.create(
            title="Corrupt",
            file=SimpleUploadedFile("corrupt.pdf", b"not a pdf", content_type="application/pdf"),
        )
        with self.assertRaises(PageExtractionFailed):
            ingest_document(corrupt.id)
        corrupt.refresh_from_db()
        self.assertEqual(corrupt.context_status, "failed")

    @patch("api.paper_context.ingestion._ocr_page")
    @patch("api.paper_context.ingestion.get_app_data_dir")
    def test_scanned_page_uses_page_level_ocr_fallback(self, app_data, ocr_page):
        app_data.return_value = Path(self.temp.name)
        ocr_page.return_value = (
            [
                {
                    "bbox": [10, 10, 250, 40],
                    "text": "OCR fallback text",
                    "block_number": 0,
                    "source": "ocr",
                    "confidence": 0.91,
                }
            ],
            0.91,
        )
        ingest_document(self.document.id, allow_ocr=True)
        scanned = self.document.context_pages.get(page_number=5)
        self.assertTrue(scanned.ocr_used)
        self.assertEqual(scanned.source_type, "ocr")
        self.assertIn("OCR fallback text", scanned.extracted_text)

    @patch("api.paper_context.ingestion.get_app_data_dir")
    def test_builder_prioritizes_explicit_pages_and_selection(self, app_data):
        app_data.return_value = Path(self.temp.name)
        ingest_document(self.document.id, allow_ocr=False)
        context = build_paper_context(
            document_id=self.document.id,
            question="Explain @page 1 with @selection",
            current_page=2,
            selected_text="A selected sentence.",
            selected_text_page=2,
        )
        self.assertEqual(context.referenced_pages, [1])
        self.assertEqual(context.page_text[0].page_number, 1)
        assert context.selected_text is not None
        self.assertEqual(context.selected_text.page_number, 2)
        self.assertFalse(context.retrieved_chunks)

    @patch("api.paper_context.ingestion.get_app_data_dir")
    def test_clear_paper_context_removes_db_rows_and_cache(self, app_data):
        app_data.return_value = Path(self.temp.name)
        ingest_document(self.document.id, allow_ocr=False)
        cache_dir = Path(self.temp.name) / "paper_context"
        self.assertTrue(cache_dir.exists())
        result = clear_paper_context(include_ai_sessions=False)
        self.document.refresh_from_db()
        self.assertGreater(result["pages_removed"], 0)
        self.assertGreater(result["chunks_removed"], 0)
        self.assertEqual(self.document.context_status, "not_started")
        self.assertFalse(models.DocumentPage.objects.exists())
        self.assertFalse(models.DocumentChunk.objects.exists())
        self.assertFalse(cache_dir.exists())


class CodexProviderTests(TestCase):
    def setUp(self):
        self.document = models.Document.objects.create(title="Codex Paper")
        self.conversation = models.ChatLogs.objects.create(
            name="Discussion",
            provider="codex",
            document=self.document,
            codex_thread_id="thread-1",
        )

    @patch("api.providers.codex.get_app_data_dir")
    def test_streaming_uses_restricted_read_only_policy_and_persists_citations(self, app_data):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        app_data.return_value = Path(temp.name)

        delta = SimpleNamespace(
            method="item/agentMessage/delta",
            payload=SimpleNamespace(delta="Evidence is reported [p. 1]."),
        )
        completed = SimpleNamespace(
            method="turn/completed",
            payload=SimpleNamespace(
                turn=SimpleNamespace(
                    status=SimpleNamespace(value="completed"),
                    error=None,
                )
            ),
        )

        class FakeClient:
            def __init__(self):
                self.params: dict | None = None
                self.inputs: list | None = None
                self.notifications = iter([delta, completed])

            def turn_start(self, thread_id, inputs, params):
                self.params = params
                self.inputs = inputs
                return SimpleNamespace(turn=SimpleNamespace(id="turn-1"))

            def register_turn_notifications(self, turn_id):
                return None

            def next_turn_notification(self, turn_id):
                return next(self.notifications)

            def unregister_turn_notifications(self, turn_id):
                return None

        client = FakeClient()
        thread = SimpleNamespace(id="thread-1", _client=client)
        provider = CodexProvider()
        context = PaperContext(
            document_id=self.document.id,
            document_title=self.document.title,
            user_question="What is reported?",
            referenced_pages=[1],
            page_text=[
                PageContext(
                    document_id=self.document.id,
                    document_hash="abc",
                    document_title=self.document.title,
                    page_number=1,
                    text="Evidence is reported.",
                    text_blocks=[],
                    source_type="embedded",
                    ocr_used=False,
                    ocr_confidence=None,
                    visually_complex=False,
                )
            ],
        )
        source_image = Path(temp.name) / "page-1.png"
        source_image.write_bytes(b"\x89PNG\r\n\x1a\n")
        context.page_images = [str(source_image)]
        with patch.object(provider, "_ensure_chatgpt_account"), patch.object(
            provider,
            "_require_sdk",
            return_value=SimpleNamespace(_client=client),
        ):
            events = list(
                provider.send_message(
                    self.conversation.id,
                    "What is reported?",
                    context,
                    model="gpt-5.4",
                )
            )

        self.assertEqual(events[-1]["type"], "completed")
        self.assertTrue(events[-1]["citations"][0]["valid"])
        assert client.params is not None
        assert client.inputs is not None
        self.assertEqual(client.params["sandboxPolicy"], READ_ONLY_SANDBOX_POLICY)
        self.assertFalse(client.params["sandboxPolicy"]["networkAccess"])
        self.assertEqual(client.inputs[1]["type"], "localImage")
        self.assertTrue(Path(client.inputs[1]["path"]).is_file())
        self.assertEqual(client.params["cwd"], str((Path(temp.name) / "ai_sessions" / str(self.conversation.id)).resolve()))
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.content[-1]["role"], "model")

    def test_api_key_account_mode_is_explicitly_blocked(self):
        account_root = SimpleNamespace(
            model_dump=lambda **kwargs: {"type": "apiKey"}
        )
        provider = CodexProvider()
        provider._sdk = SimpleNamespace(
            _client=SimpleNamespace(_proc=None),
            account=lambda refresh_token=False: SimpleNamespace(
                account=SimpleNamespace(root=account_root),
                requires_openai_auth=True,
            ),
        )
        status = provider.get_status()
        self.assertEqual(status["state"], "api_key_mode")
        self.assertFalse(status["subscription_usable"])

    def test_rate_limits_are_read_through_compatibility_adapter(self):
        class RateResponse:
            def model_dump(self, **kwargs):
                return {"rateLimits": {"primary": {"usedPercent": 42}}}

        client = SimpleNamespace(
            request=lambda *args, **kwargs: RateResponse(),
            _proc=None,
        )
        account_root = SimpleNamespace(
            model_dump=lambda **kwargs: {
                "type": "chatgpt",
                "email": "reader@example.com",
                "planType": "plus",
            }
        )
        provider = CodexProvider()
        provider._sdk = SimpleNamespace(
            _client=client,
            account=lambda refresh_token=False: SimpleNamespace(
                account=SimpleNamespace(root=account_root),
                requires_openai_auth=True,
            ),
        )
        limits = provider.rate_limits()
        assert limits is not None
        self.assertEqual(
            limits["rateLimits"]["primary"]["usedPercent"],
            42,
        )

    def test_cancellation_interrupts_only_the_active_turn(self):
        interrupted = []
        provider = CodexProvider()
        provider._sdk = SimpleNamespace(
            _client=SimpleNamespace(
                turn_interrupt=lambda thread_id, turn_id: interrupted.append(
                    (thread_id, turn_id)
                )
            )
        )
        provider._active_turns[self.conversation.id] = ("thread-1", "turn-1")
        provider.cancel_generation(self.conversation.id)
        self.assertEqual(interrupted, [("thread-1", "turn-1")])

    def test_runtime_crash_reports_restartable_state(self):
        closed = []
        provider = CodexProvider()
        provider._sdk = SimpleNamespace(
            _client=SimpleNamespace(_proc=SimpleNamespace(poll=lambda: 1)),
            close=lambda: closed.append(True),
        )
        status = provider.get_status()
        self.assertEqual(status["state"], "runtime_error")
        self.assertFalse(status["connected"])
        self.assertTrue(closed)
