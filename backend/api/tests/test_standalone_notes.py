from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from api.models import ChatLogs, StandaloneNote


class StandaloneNoteAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_create_update_list_and_delete_note(self):
        created = self.client.post(
            reverse("notes-list"),
            {"title": "  Research question  ", "content": "# Draft"},
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data["title"], "Research question")

        note_id = created.data["id"]
        updated = self.client.patch(
            reverse("notes-detail", args=[note_id]),
            {"content": "# Revised\n\nA standalone idea."},
            format="json",
        )
        self.assertEqual(updated.status_code, 200)
        note = StandaloneNote.objects.get(pk=note_id)
        self.assertEqual(note.content, "# Revised\n\nA standalone idea.")
        self.assertTrue(note.needs_embedding)

        listed = self.client.get(reverse("notes-list"))
        self.assertEqual([item["id"] for item in listed.data], [note_id])
        self.assertEqual(self.client.delete(reverse("notes-detail", args=[note_id])).status_code, 204)

    def test_knowledge_search_feed_contains_standalone_notes(self):
        note = StandaloneNote.objects.create(title="Causal inference", content="Potential outcomes")
        response = self.client.get(reverse("search-notes"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            {
                "item_type": "note",
                "title": note.title,
                "note_id": note.pk,
                "content": note.content,
                "created_at": note.created_at,
                "updated_at": note.updated_at,
            },
            response.data,
        )


class StandaloneNoteChatTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.note = StandaloneNote.objects.create(
            title="Interpretability",
            content="Sparse autoencoders may expose learned features.",
        )
        self.preferences = {"user_preferences": {"ai": {"default_provider": "gemini"}}}

    @patch("api.views.add_message_to_chat")
    @patch("api.views.send_prompt", return_value="A useful answer")
    @patch("api.views.name_chat", return_value="Note discussion")
    @patch("api.views.get_provider_api_key", return_value="key")
    @patch("api.views.load_user_preferences")
    @patch("api.views.load_env_vars", return_value={})
    def test_chat_is_owned_by_note_and_receives_note_context(
        self, _env, preferences, _key, _name, send_prompt, _add_message
    ):
        preferences.return_value = self.preferences
        response = self.client.post(
            reverse("ask-ai"),
            {"prompt": "Challenge this", "note_id": self.note.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        chat = ChatLogs.objects.get(pk=response.data["chat_id"])
        self.assertEqual(chat.note, self.note)
        sent_prompt = send_prompt.call_args.kwargs["prompt"]
        self.assertIn("CURRENT NOTE", sent_prompt)
        self.assertIn("Sparse autoencoders", sent_prompt)

    @patch("api.views.get_provider_api_key", return_value="key")
    @patch("api.views.load_user_preferences")
    @patch("api.views.load_env_vars", return_value={})
    def test_unknown_note_returns_404(self, _env, preferences, _key):
        preferences.return_value = self.preferences
        response = self.client.post(
            reverse("ask-ai"),
            {"prompt": "Hello", "note_id": 99999},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
