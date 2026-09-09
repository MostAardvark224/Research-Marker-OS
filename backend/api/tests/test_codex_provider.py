from types import SimpleNamespace
from pathlib import Path
from unittest.mock import Mock, patch
import subprocess

from django.test import SimpleTestCase, TestCase

from api.errors import ResearchMarkerError
from api.models import ChatLogs, Document
from api.paper_context.types import PaperContext
from api.providers.codex import CodexProvider, _newer_installed_codex


class CodexCatalogTests(SimpleTestCase):
    def test_catalog_preserves_reasoning_options_and_reads_all_pages(self):
        def model(name, hidden=False):
            return SimpleNamespace(
                model=name, display_name=name, description="Model", is_default=False,
                input_modalities=["text"], hidden=hidden,
                default_reasoning_effort=SimpleNamespace(value="low"),
                supported_reasoning_efforts=[SimpleNamespace(
                    reasoning_effort=SimpleNamespace(value="ultra"), description="Deepest reasoning",
                )],
            )

        sdk = Mock()
        sdk.models.return_value = SimpleNamespace(data=[model("first")], next_cursor="page-2")
        sdk._client.request.return_value = SimpleNamespace(
            data=[model("astra"), model("hidden", hidden=True)], next_cursor=None,
        )
        provider = CodexProvider()
        with patch.object(provider, "_require_sdk", return_value=sdk):
            catalog = provider.models()
        self.assertEqual([item["id"] for item in catalog], ["first", "astra"])
        self.assertEqual(catalog[1]["default_reasoning_effort"], "low")
        self.assertEqual(catalog[1]["supported_reasoning_efforts"], [
            {"effort": "ultra", "description": "Deepest reasoning"},
        ])
        self.assertEqual(sdk._client.request.call_args.args, (
            "model/list", {"cursor": "page-2", "includeHidden": False},
        ))

    @patch("api.providers.codex.Path.is_file", return_value=True)
    @patch("api.providers.codex.shutil.which", return_value="/usr/bin/codex")
    @patch("api.providers.codex.subprocess.run")
    def test_prefers_newer_cli_and_falls_back_for_old_or_unusable_cli(self, run, _which, _exists):
        run.return_value = SimpleNamespace(returncode=0, stdout="codex-cli 0.153.4\n")
        self.assertEqual(_newer_installed_codex("0.144.4"), "/usr/bin/codex")
        run.return_value = SimpleNamespace(returncode=0, stdout="codex-cli 0.140.0\n")
        self.assertIsNone(_newer_installed_codex("0.144.4"))
        run.side_effect = subprocess.TimeoutExpired("codex", 3)
        self.assertIsNone(_newer_installed_codex("0.144.4"))


class CodexReasoningTests(TestCase):
    def test_default_effort_resets_previous_turn_and_invalid_effort_never_starts_turn(self):
        document = Document.objects.create(title="Paper")
        conversation = ChatLogs.objects.create(provider="codex", document=document, codex_thread_id="thread")
        context = PaperContext(document_id=document.id, document_title="Paper", user_question="Question")
        provider = CodexProvider()
        client = Mock()
        client.turn_start.return_value = SimpleNamespace(turn=SimpleNamespace(id="turn"))
        client.next_turn_notification.return_value = SimpleNamespace(
            method="turn/completed",
            payload=SimpleNamespace(turn=SimpleNamespace(status=SimpleNamespace(value="completed"))),
        )
        with patch.object(provider, "_ensure_chatgpt_account"), patch.object(
            provider, "_require_sdk", return_value=SimpleNamespace(_client=client),
        ), patch.object(provider, "_prepare_session", return_value=(Path('/tmp'), [])), patch.object(
            provider, "models", return_value=[{
                "id": "astra", "is_default": True, "default_reasoning_effort": "low",
                "supported_reasoning_efforts": [{"effort": "low"}, {"effort": "ultra"}],
            }],
        ):
            list(provider.send_message(conversation.id, "Question", context, reasoning_effort="ultra"))
            self.assertEqual(client.turn_start.call_args.kwargs["params"]["effort"], "ultra")
            list(provider.send_message(conversation.id, "Question", context))
            self.assertEqual(client.turn_start.call_args.kwargs["params"]["effort"], "low")
            client.turn_start.reset_mock()
            with self.assertRaises(ResearchMarkerError):
                list(provider.send_message(conversation.id, "Question", context, reasoning_effort="invalid"))
            client.turn_start.assert_not_called()
