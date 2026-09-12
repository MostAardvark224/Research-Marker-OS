import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
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

    def test_imports_uploaded_markdown_files_into_selected_folder(self):
        folder = Folder.objects.create(name="Imported")
        uploads = [
            SimpleUploadedFile("first.md", b"# First\n\nBody", "text/markdown"),
            SimpleUploadedFile("second.MD", b"Second body", "text/markdown"),
        ]

        response = self.client.post(
            reverse("notes-import"),
            {"folder": str(folder.id), "files": uploads},
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["count"], 2)
        notes = list(StandaloneNote.objects.order_by("sort_order"))
        self.assertEqual([note.title for note in notes], ["first", "second"])
        self.assertEqual([note.content for note in notes], ["# First\n\nBody", "Second body"])
        self.assertTrue(all(note.folder_id == folder.id for note in notes))

    def test_imports_absolute_file_paths_and_directories_recursively(self):
        folder = Folder.objects.create(name="Imported")
        StandaloneNote.objects.create(title="Existing", folder=folder, sort_order=0)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            explicit = root / "explicit.md"
            explicit.write_text("Explicit", encoding="utf-8")
            nested = root / "nested"
            nested.mkdir()
            (nested / "child.md").write_text("Nested", encoding="utf-8")
            (nested / "ignore.txt").write_text("Ignore", encoding="utf-8")

            response = self.client.post(
                reverse("notes-import"),
                {
                    "folder": folder.id,
                    "paths": [str(explicit)],
                    "directories": [str(root)],
                },
                format="json",
            )

        self.assertEqual(response.status_code, 201)
        # explicit.md is found twice but imported only once.
        imported = list(StandaloneNote.objects.filter(folder=folder).order_by("sort_order"))[1:]
        self.assertEqual([note.title for note in imported], ["explicit", "child"])
        self.assertEqual([note.sort_order for note in imported], [1, 2])

    def test_import_can_create_a_new_destination_folder(self):
        parent = Folder.objects.create(name="Research")
        upload = SimpleUploadedFile("ideas.md", b"# Ideas", "text/markdown")

        response = self.client.post(
            reverse("notes-import"),
            {
                "new_folder_name": "Imported notes",
                "new_folder_parent": str(parent.id),
                "files": [upload],
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        folder = Folder.objects.get(name="Imported notes")
        note = StandaloneNote.objects.get(title="ideas")
        self.assertEqual(folder.parent_id, parent.id)
        self.assertEqual(note.folder_id, folder.id)
        self.assertEqual(
            response.data["folder"],
            {"id": folder.id, "name": "Imported notes", "parent": parent.id},
        )

    def test_new_import_folder_validation_does_not_create_notes(self):
        Folder.objects.create(name="Imported notes")
        upload = SimpleUploadedFile("ideas.md", b"# Ideas", "text/markdown")

        response = self.client.post(
            reverse("notes-import"),
            {"new_folder_name": "Imported notes", "files": [upload]},
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("already exists", response.data["error"])
        self.assertEqual(Folder.objects.filter(name="Imported notes").count(), 1)
        self.assertEqual(StandaloneNote.objects.count(), 0)

    def test_import_rejects_existing_and_new_folder_together(self):
        folder = Folder.objects.create(name="Existing")
        upload = SimpleUploadedFile("ideas.md", b"# Ideas", "text/markdown")

        response = self.client.post(
            reverse("notes-import"),
            {
                "folder": str(folder.id),
                "new_folder_name": "New destination",
                "files": [upload],
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Folder.objects.count(), 1)
        self.assertEqual(StandaloneNote.objects.count(), 0)

    def test_import_rejects_relative_non_markdown_and_invalid_utf8_sources_atomically(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            text_file = root / "not-markdown.txt"
            text_file.write_text("No", encoding="utf-8")

            relative = self.client.post(
                reverse("notes-import"), {"paths": ["notes/example.md"]}, format="json"
            )
            wrong_suffix = self.client.post(
                reverse("notes-import"), {"paths": [str(text_file)]}, format="json"
            )
            invalid_utf8 = self.client.post(
                reverse("notes-import"),
                {
                    "files": [
                        SimpleUploadedFile("bad.md", b"\xff\xfe", "text/markdown"),
                        SimpleUploadedFile("good.md", b"Good", "text/markdown"),
                    ]
                },
                format="multipart",
            )

        self.assertEqual(relative.status_code, 400)
        self.assertIn("absolute", relative.data["error"])
        self.assertEqual(wrong_suffix.status_code, 400)
        self.assertIn("Only .md", wrong_suffix.data["error"])
        self.assertEqual(invalid_utf8.status_code, 400)
        self.assertEqual(StandaloneNote.objects.count(), 0)

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
