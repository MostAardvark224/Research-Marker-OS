import json
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from api.errors import ProviderNotAuthenticated
from api.models import ChatLogs, Document
from api.paper_context.types import PaperContext


class CodexAccountAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    @patch("api.codex_views.get_codex_provider")
    def test_status_get_and_connect_post(self, get_provider):
        provider = get_provider.return_value
        provider.get_status.return_value = {"connected": False}
        provider.connect.return_value = {"connected": True}

        status_response = self.client.get(reverse("codex-status"))
        connect_response = self.client.post(reverse("codex-status"), {}, format="json")

        self.assertEqual(status_response.data, {"connected": False})
        self.assertEqual(connect_response.data, {"connected": True})
        provider.connect.assert_called_once_with()

    @patch("api.codex_views.get_codex_provider")
    def test_device_login_and_cancel(self, get_provider):
        provider = get_provider.return_value
        provider.start_device_code_login.return_value = {"login_id": "login-1"}

        started = self.client.post(reverse("codex-login"), {"mode": "device_code"}, format="json")
        cancelled = self.client.delete(
            reverse("codex-login"), {"login_id": "login-1"}, format="json"
        )

        self.assertEqual(started.status_code, 202)
        self.assertEqual(cancelled.status_code, 204)
        provider.cancel_login.assert_called_once_with("login-1")

    @patch("api.codex_views.get_codex_provider")
    def test_provider_error_preserves_domain_status(self, get_provider):
        get_provider.return_value.rate_limits.side_effect = ProviderNotAuthenticated("Sign in")
        response = self.client.get(reverse("codex-rate-limits"))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["error"], "provider_not_authenticated")

    @patch("api.codex_views.get_codex_provider")
    def test_models_and_logout(self, get_provider):
        provider = get_provider.return_value
        provider.models.return_value = [{"id": "model"}]
        provider.get_status.return_value = {"connected": False}

        models = self.client.get(reverse("codex-models"))
        logout = self.client.post(reverse("codex-logout"), {}, format="json")

        self.assertEqual(models.data["models"], [{"id": "model"}])
        self.assertEqual(logout.status_code, 200)
        provider.logout.assert_called_once_with()


class CodexConversationAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.document = Document.objects.create(title="Paper", file="documents/paper.pdf")
        self.conversation = ChatLogs.objects.create(
            name="Conversation", provider="codex", document=self.document, codex_thread_id="thread-1"
        )

    @patch("api.codex_views.get_codex_provider")
    def test_list_and_create_conversations(self, get_provider):
        provider = get_provider.return_value
        provider.list_conversations.return_value = [{"id": self.conversation.id}]
        provider.create_conversation.return_value = self.conversation

        listing = self.client.get(reverse("codex-conversations"))
        created = self.client.post(
            reverse("codex-conversations"),
            {"document_id": self.document.id, "title": "New"},
            format="json",
        )

        self.assertEqual(listing.status_code, 200)
        self.assertEqual(created.status_code, 201)
        provider.create_conversation.assert_called_once_with(self.document.id, "New")

    @patch("api.codex_views.get_codex_provider")
    def test_create_rejects_unknown_document(self, get_provider):
        response = self.client.post(
            reverse("codex-conversations"), {"document_id": 999999}, format="json"
        )
        self.assertEqual(response.status_code, 404)
        get_provider.return_value.create_conversation.assert_not_called()

    def test_detail_only_returns_codex_conversations(self):
        legacy = ChatLogs.objects.create(name="Legacy", provider="legacy")
        found = self.client.get(
            reverse("codex-conversation-detail", kwargs={"conversation_id": self.conversation.id})
        )
        missing = self.client.get(
            reverse("codex-conversation-detail", kwargs={"conversation_id": legacy.id})
        )
        self.assertEqual(found.status_code, 200)
        self.assertEqual(missing.status_code, 404)

    @patch("api.codex_views.build_paper_context")
    @patch("api.codex_views.get_codex_provider")
    def test_stream_returns_ndjson_and_required_headers(self, get_provider, build_context):
        build_context.return_value = PaperContext(
            document_id=self.document.id, document_title="Paper", user_question="Question"
        )
        provider = get_provider.return_value
        provider.send_message.return_value = iter(
            [{"type": "text", "text": "Answer"}, {"type": "complete"}]
        )

        response = self.client.post(
            reverse("codex-conversation-stream", kwargs={"conversation_id": self.conversation.id}),
            {"question": "Question", "model": "codex-model", "reasoning_effort": "high"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/x-ndjson")
        self.assertEqual(response["Cache-Control"], "no-cache, no-transform")
        events = [json.loads(line) for line in b"".join(response.streaming_content).splitlines()]
        self.assertEqual([event["type"] for event in events], ["text", "complete"])
        self.assertEqual(provider.send_message.call_args.kwargs["reasoning_effort"], "high")

    @patch("api.codex_views.build_paper_context")
    @patch("api.codex_views.get_codex_provider")
    async def test_asgi_stream_delivers_deltas_before_generation_finishes(self, get_provider, build_context):
        build_context.return_value = PaperContext(
            document_id=self.document.id, document_title="Paper", user_question="Question"
        )
        produced = []
        closed = []

        def generate():
            try:
                for event in (
                    {"type": "started", "turn_id": "turn-1"},
                    {"type": "delta", "text": "First "},
                    {"type": "delta", "text": "second"},
                    {"type": "completed", "citations": []},
                ):
                    produced.append(event)
                    yield event
            finally:
                closed.append(True)

        get_provider.return_value.send_message.return_value = generate()
        response = await self.async_client.post(
            reverse("codex-conversation-stream", kwargs={"conversation_id": self.conversation.id}),
            {"question": "Question", "model": "codex-model"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_async)
        self.assertEqual(response["X-Accel-Buffering"], "no")
        self.assertEqual(produced, [])
        chunks = response.streaming_content.__aiter__()
        self.assertEqual(json.loads(await anext(chunks))["type"], "started")
        self.assertEqual(json.loads(await anext(chunks))["text"], "First ")
        self.assertEqual(len(produced), 2)
        self.assertEqual(closed, [])
        self.assertEqual(json.loads(await anext(chunks))["text"], "second")
        self.assertEqual(json.loads(await anext(chunks))["type"], "completed")
        with self.assertRaises(StopAsyncIteration):
            await anext(chunks)
        self.assertEqual(closed, [True])

    @patch("api.codex_views.build_paper_context")
    @patch("api.codex_views.get_codex_provider")
    async def test_asgi_stream_preserves_partial_text_before_error(self, get_provider, build_context):
        build_context.return_value = PaperContext(
            document_id=self.document.id, document_title="Paper", user_question="Question"
        )

        def generate():
            yield {"type": "delta", "text": "Partial"}
            raise RuntimeError("process stopped")

        get_provider.return_value.send_message.return_value = generate()
        response = await self.async_client.post(
            reverse("codex-conversation-stream", kwargs={"conversation_id": self.conversation.id}),
            {"question": "Question", "model": "codex-model"},
            content_type="application/json",
        )
        events = [json.loads(chunk) async for chunk in response.streaming_content]
        self.assertEqual(events[0], {"type": "delta", "text": "Partial"})
        self.assertEqual(events[1]["type"], "error")
        self.assertEqual(events[1]["message"], "process stopped")

    @patch("api.codex_views.build_paper_context")
    @patch("api.codex_views.get_codex_provider")
    def test_stream_serializes_late_provider_failure_as_error_event(self, get_provider, build_context):
        build_context.return_value = PaperContext(
            document_id=self.document.id, document_title="Paper", user_question="Question"
        )

        def failing_stream():
            yield {"type": "text", "text": "Partial"}
            raise RuntimeError("process stopped")

        get_provider.return_value.send_message.return_value = failing_stream()
        response = self.client.post(
            reverse("codex-conversation-stream", kwargs={"conversation_id": self.conversation.id}),
            {"question": "Question", "model": "codex-model"},
            format="json",
        )
        events = [json.loads(line) for line in b"".join(response.streaming_content).splitlines()]
        self.assertEqual(events[-1]["type"], "error")
        self.assertEqual(events[-1]["error"], "provider_unavailable")

    @patch("api.codex_views.get_codex_provider")
    def test_cancel_delegates_to_provider(self, get_provider):
        response = self.client.post(
            reverse("codex-conversation-cancel", kwargs={"conversation_id": self.conversation.id}),
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        get_provider.return_value.cancel_generation.assert_called_once_with(self.conversation.id)
