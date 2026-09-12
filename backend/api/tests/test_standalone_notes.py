from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from api.models import ChatLogs, Folder, StandaloneNote


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

    def test_note_can_be_organized_into_folders_like_documents(self):
        folder = Folder.objects.create(name="Research")

        created = self.client.post(
            reverse("notes-list"),
            {"title": "In folder", "folder": folder.id},
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        note = StandaloneNote.objects.get(pk=created.data["id"])
        self.assertEqual(note.folder_id, folder.id)
        self.assertEqual(note.sort_order, 0)

        second = StandaloneNote.objects.create(title="Also in folder", folder=folder, sort_order=1)

        detail = self.client.get(reverse("folders-detail", kwargs={"pk": folder.id}))
        self.assertEqual(
            {item["id"] for item in detail.data["notes"]}, {note.id, second.id}
        )

        complete = self.client.get(reverse("complete-fetch"))
        self.assertEqual(complete.data["folders"][0]["notes"][0]["id"], note.id)

    def test_create_note_with_explicit_null_folder_lands_in_unassigned(self):
        # The New Note modal sends folder=null when "Unassigned" is picked.
        StandaloneNote.objects.create(title="Existing loose note", sort_order=0)

        created = self.client.post(
            reverse("notes-list"),
            {"title": "Loose too", "content": "", "folder": None},
            format="json",
        )

        self.assertEqual(created.status_code, 201)
        note = StandaloneNote.objects.get(pk=created.data["id"])
        self.assertIsNone(note.folder_id)
        self.assertEqual(note.sort_order, 1)

    def test_moving_note_out_of_a_folder_reassigns_sort_order(self):
        # Dragging a note onto "Unassigned" patches folder back to null.
        folder = Folder.objects.create(name="Research")
        StandaloneNote.objects.create(title="Already unassigned", sort_order=0)
        note = StandaloneNote.objects.create(title="Movable", folder=folder, sort_order=0)

        moved = self.client.patch(
            reverse("notes-detail", args=[note.id]),
            {"folder": None},
            format="json",
        )

        self.assertEqual(moved.status_code, 200)
        note.refresh_from_db()
        self.assertIsNone(note.folder_id)
        self.assertEqual(note.sort_order, 1)

    def test_moving_note_between_folders_reassigns_sort_order(self):
        first_folder = Folder.objects.create(name="First")
        second_folder = Folder.objects.create(name="Second")
        StandaloneNote.objects.create(title="Sibling", folder=second_folder, sort_order=0)
        note = StandaloneNote.objects.create(title="Movable", folder=first_folder, sort_order=0)

        moved = self.client.patch(
            reverse("notes-detail", args=[note.id]),
            {"folder": second_folder.id},
            format="json",
        )

        self.assertEqual(moved.status_code, 200)
        note.refresh_from_db()
        self.assertEqual(note.folder_id, second_folder.id)
        self.assertEqual(note.sort_order, 1)

    def test_unassigned_notes_appear_in_complete_fetch(self):
        note = StandaloneNote.objects.create(title="Loose note")
        response = self.client.get(reverse("complete-fetch"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data["UnassignedNotes"]], [note.id])

    def test_reorder_notes_updates_order_only_within_folder(self):
        folder = Folder.objects.create(name="Folder")
        first = StandaloneNote.objects.create(title="First", folder=folder)
        second = StandaloneNote.objects.create(title="Second", folder=folder)

        response = self.client.post(
            reverse("notes-reorder"),
            {"folder_id": folder.id, "note_ids": [second.id, first.id]},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual((second.sort_order, first.sort_order), (0, 1))

    def test_reorder_notes_rejects_empty_or_cross_folder_ids(self):
        folder = Folder.objects.create(name="Folder")
        other = Folder.objects.create(name="Other")
        note = StandaloneNote.objects.create(title="Note", folder=other)

        empty = self.client.post(
            reverse("notes-reorder"), {"folder_id": folder.id, "note_ids": []}, format="json"
        )
        wrong_folder = self.client.post(
            reverse("notes-reorder"),
            {"folder_id": folder.id, "note_ids": [note.id]},
            format="json",
        )

        self.assertEqual(empty.status_code, 400)
        self.assertEqual(wrong_folder.status_code, 400)

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

    @patch("api.views.add_message_to_chat")
    @patch("api.views.send_prompt", return_value="A useful answer")
    @patch("api.views.name_chat", return_value="Knowledge base chat")
    @patch("api.views.get_provider_api_key", return_value="key")
    @patch("api.views.load_user_preferences")
    @patch("api.views.load_env_vars", return_value={})
    def test_note_ids_context_tag_injects_referenced_note_content(
        self, _env, preferences, _key, _name, send_prompt, _add_message
    ):
        # Mirrors how the Knowledge Base chat's @note:"Title" resolves to note_ids,
        # the same way @paper:"Title" resolves to paper_ids.
        preferences.return_value = self.preferences
        response = self.client.post(
            reverse("ask-ai"),
            {"prompt": "Summarize @note", "note_ids": [self.note.pk]},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        sent_prompt = send_prompt.call_args.kwargs["prompt"]
        self.assertIn(self.note.title, sent_prompt)
        self.assertIn("Sparse autoencoders", sent_prompt)

    @patch("api.views.get_provider_api_key", return_value="key")
    @patch("api.views.load_user_preferences")
    @patch("api.views.load_env_vars", return_value={})
    def test_note_ids_and_at_recent_together_are_rejected(self, _env, preferences, _key):
        preferences.return_value = self.preferences
        response = self.client.post(
            reverse("ask-ai"),
            {"prompt": "Hello", "note_ids": [self.note.pk], "at_recent": True},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
