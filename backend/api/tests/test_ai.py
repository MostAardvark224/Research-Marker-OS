from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from api.models import ChatLogs


class LegacyAIChatAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("ask-ai")
        self.preferences = {"user_preferences": {"ai": {"default_provider": "gemini"}}}

    @patch("api.views.load_user_preferences")
    @patch("api.views.load_env_vars", return_value={})
    def test_missing_api_key_returns_400(self, _env, preferences):
        preferences.return_value = self.preferences
        response = self.client.post(self.url, {"prompt": "Hello"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("API key", response.data["error"])

    @patch("api.views.get_provider_api_key", return_value="key")
    @patch("api.views.load_user_preferences")
    @patch("api.views.load_env_vars", return_value={})
    def test_missing_prompt_returns_400(self, _env, preferences, _key):
        preferences.return_value = self.preferences
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "Prompt is required")

    @patch("api.views.add_message_to_chat")
    @patch("api.views.send_prompt", return_value="Model answer")
    @patch("api.views.name_chat", return_value="Generated title")
    @patch("api.views.get_provider_api_key", return_value="key")
    @patch("api.views.load_user_preferences")
    @patch("api.views.load_env_vars", return_value={})
    def test_normal_prompt_creates_chat_and_saves_both_messages(
        self, _env, preferences, _key, name_chat, send_prompt, add_message
    ):
        preferences.return_value = self.preferences

        response = self.client.post(self.url, {"prompt": "Explain this"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["model_response"], "Model answer")
        chat = ChatLogs.objects.get()
        self.assertEqual(chat.name, "Generated title")
        name_chat.assert_called_once()
        send_prompt.assert_called_once()
        self.assertEqual(add_message.call_count, 2)
        add_message.assert_any_call(chat.id, "user", "Explain this")
        add_message.assert_any_call(chat.id, "model", "Model answer")

    @patch("api.views.name_chat", return_value="Generated title")
    @patch("api.views.get_provider_api_key", return_value="key")
    @patch("api.views.load_user_preferences")
    @patch("api.views.load_env_vars", return_value={})
    def test_multiple_context_modes_are_rejected(self, _env, preferences, _key, _name):
        preferences.return_value = self.preferences
        response = self.client.post(
            self.url,
            {"prompt": "Explain", "at_recent": True, "paper_ids": [1]},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("only have one", response.data["error"])

    @patch("api.views.get_provider_api_key", return_value="key")
    @patch("api.views.load_user_preferences")
    @patch("api.views.load_env_vars", return_value={})
    def test_unknown_chat_id_returns_404(self, _env, preferences, _key):
        preferences.return_value = self.preferences
        response = self.client.post(
            self.url, {"prompt": "Continue", "chat_id": 999999}, format="json"
        )
        self.assertEqual(response.status_code, 404)


class ModelCatalogAPITests(TestCase):
    @patch("api.providers.codex.get_codex_provider")
    @patch("api.views.get_all_provider_models", return_value=[{"id": "gemini", "models": ["g"]}])
    @patch("api.views.load_env_vars", return_value={})
    @patch("api.providers.embeddings.embedding_provider_catalog", return_value=[{"id": "local"}])
    def test_ai_models_combines_chat_codex_and_embedding_catalogs(
        self, _embedding, _env, _models, get_codex
    ):
        provider = get_codex.return_value
        provider.get_status.return_value = {"subscription_usable": True}
        provider.models.return_value = [{"id": "codex-model", "is_default": True}]

        response = APIClient().get(reverse("ai-models"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data["providers"]], ["gemini", "codex"])
        self.assertEqual(response.data["embedding_providers"], [{"id": "local"}])
