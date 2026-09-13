import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from api.models import Annotations, Document, NoteSyncBinding, NoteSyncRevision
from api.note_sync import (
    get_document_sync_state,
    refresh_all_notes,
    refresh_document_note,
    resolve_document_conflict,
    sanitize_note_sync_directories,
    scan_markdown_notes,
)


class NoteSyncTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.document = Document.objects.create(title="Paper", file="documents/paper.pdf")

    def tearDown(self):
        self.directory.cleanup()

    def write_note(self, body, name="paper.md"):
        path = self.root / name
        path.write_text(
            f"#rm:{self.document.note_sync_code}\n{body}",
            encoding="utf-8",
        )
        return path

    def scan(self):
        with patch(
            "api.note_sync.load_note_sync_directories",
            return_value=([str(self.root)], []),
        ):
            return scan_markdown_notes()

    def refresh(self):
        return refresh_document_note(self.document, self.scan())

    def resolve(self, action):
        with patch(
            "api.note_sync.load_note_sync_directories",
            return_value=([str(self.root)], []),
        ):
            return resolve_document_conflict(self.document, action)

    def test_documents_receive_stable_unique_codes(self):
        other = Document.objects.create(title="Other", file="documents/other.pdf")
        self.assertEqual(len(self.document.note_sync_code), 10)
        self.assertNotEqual(self.document.note_sync_code, other.note_sync_code)

    def test_initial_import_strips_marker_and_saves_revision(self):
        self.write_note("# Cursor notes\n\nBody")

        result = self.refresh()

        annotation = Annotations.objects.get(document=self.document)
        self.assertEqual(result["status"], "imported")
        self.assertEqual(annotation.notepad, "# Cursor notes\n\nBody")
        self.assertNotIn("#rm:", annotation.notepad)
        self.assertTrue(NoteSyncBinding.objects.filter(document=self.document).exists())
        self.assertEqual(NoteSyncRevision.objects.get().content, "")

    def test_scan_finds_nested_uppercase_extension_and_case_insensitive_marker(self):
        nested = self.root / "nested"
        nested.mkdir()
        path = nested / "paper.MD"
        path.write_text(
            f"  #rm:{self.document.note_sync_code.lower()}  \nNested notes",
            encoding="utf-8",
        )

        scan = self.scan()

        match = scan["files_by_code"][self.document.note_sync_code][0]
        self.assertEqual(match["path"], str(path))
        self.assertEqual(match["content"], "Nested notes")

    def test_scan_ignores_non_markdown_and_markdown_without_marker(self):
        (self.root / "notes.txt").write_text(
            f"#rm:{self.document.note_sync_code}\nWrong extension",
            encoding="utf-8",
        )
        (self.root / "ordinary.md").write_text("No marker", encoding="utf-8")

        scan = self.scan()

        self.assertEqual(scan["files_by_code"], {})
        self.assertEqual(scan["scan_errors"], [])

    def test_scan_rejects_a_file_with_multiple_paper_codes(self):
        other = Document.objects.create(title="Other", file="documents/other.pdf")
        (self.root / "ambiguous.md").write_text(
            f"#rm:{self.document.note_sync_code}\n#rm:{other.note_sync_code}\nBody",
            encoding="utf-8",
        )

        result = self.refresh()

        self.assertEqual(result["status"], "conflict")
        self.assertEqual(result["conflict_type"], "invalid_marker")
        self.assertFalse(Annotations.objects.filter(document=self.document).exists())

    def test_scan_reports_oversized_markdown_without_importing(self):
        self.write_note("Body")
        with patch("api.note_sync.MAX_MARKDOWN_BYTES", 1):
            scan = self.scan()

        self.assertEqual(scan["files_by_code"], {})
        self.assertIn("larger than 10 MB", scan["scan_errors"][0]["message"])

    def test_initial_mismatch_never_overwrites_and_can_keep_both(self):
        Annotations.objects.create(
            document=self.document,
            highlight_data=[],
            sticky_note_data=[],
            notepad="Research Marker draft",
        )
        path = self.write_note("Cursor draft")

        conflict = self.refresh()

        self.assertEqual(conflict["status"], "conflict")
        self.assertEqual(
            Annotations.objects.get(document=self.document).notepad,
            "Research Marker draft",
        )

        resolved = self.resolve("keep_both")

        self.assertEqual(resolved["status"], "kept_both")
        self.assertEqual(
            Annotations.objects.get(document=self.document).notepad,
            "Research Marker draft\n\n---\n\nCursor draft",
        )
        self.assertEqual(NoteSyncRevision.objects.get().content, "Research Marker draft")
        self.assertEqual(
            path.read_text(encoding="utf-8"),
            f"#rm:{self.document.note_sync_code}\nCursor draft",
        )

    def test_only_external_changes_are_imported(self):
        path = self.write_note("First")
        self.refresh()
        path.write_text(
            f"#rm:{self.document.note_sync_code}\nSecond",
            encoding="utf-8",
        )

        result = self.refresh()

        self.assertEqual(result["status"], "imported")
        self.assertEqual(Annotations.objects.get(document=self.document).notepad, "Second")

    def test_unchanged_refresh_does_not_create_another_revision(self):
        self.write_note("First")
        self.refresh()
        revision_count = NoteSyncRevision.objects.count()

        result = self.refresh()

        self.assertEqual(result["status"], "unchanged")
        self.assertEqual(NoteSyncRevision.objects.count(), revision_count)

    def test_app_only_change_is_preserved_and_source_file_is_untouched(self):
        path = self.write_note("First")
        self.refresh()
        annotation = Annotations.objects.get(document=self.document)
        annotation.notepad = "Changed in Research Marker"
        annotation.save()
        source_before = path.read_bytes()

        result = self.refresh()

        self.assertEqual(result["status"], "app_changed")
        self.assertEqual(
            Annotations.objects.get(document=self.document).notepad,
            "Changed in Research Marker",
        )
        self.assertEqual(path.read_bytes(), source_before)

    def test_two_sided_changes_create_conflict(self):
        path = self.write_note("First")
        self.refresh()
        annotation = Annotations.objects.get(document=self.document)
        annotation.notepad = "Changed in app"
        annotation.save()
        path.write_text(
            f"#rm:{self.document.note_sync_code}\nChanged in Cursor",
            encoding="utf-8",
        )

        result = self.refresh()

        self.assertEqual(result["status"], "conflict")
        self.assertEqual(result["conflict_type"], "both_changed")
        self.assertEqual(Annotations.objects.get(document=self.document).notepad, "Changed in app")

    def test_duplicate_codes_are_never_guessed(self):
        self.write_note("First", "one.md")
        self.write_note("Second", "two.md")

        result = self.refresh()

        self.assertEqual(result["status"], "conflict")
        self.assertEqual(result["conflict_type"], "duplicate_code")
        self.assertFalse(Annotations.objects.filter(document=self.document).exists())

    def test_use_markdown_saves_old_app_note_as_revision(self):
        Annotations.objects.create(
            document=self.document,
            highlight_data=[],
            sticky_note_data=[],
            notepad="App version",
        )
        path = self.write_note("Markdown version")
        source_before = path.read_bytes()
        self.refresh()

        result = self.resolve("use_markdown")

        self.assertEqual(result["status"], "imported")
        self.assertEqual(result["notepad"], "Markdown version")
        self.assertEqual(NoteSyncRevision.objects.get().content, "App version")
        self.assertEqual(path.read_bytes(), source_before)

    def test_keep_research_marker_acknowledges_versions_without_writing_file(self):
        Annotations.objects.create(
            document=self.document,
            highlight_data=[],
            sticky_note_data=[],
            notepad="App version",
        )
        path = self.write_note("Markdown version")
        source_before = path.read_bytes()
        self.refresh()

        resolved = self.resolve("keep_research_marker")
        refreshed = self.refresh()

        self.assertEqual(resolved["status"], "kept_app")
        self.assertEqual(resolved["notepad"], "App version")
        self.assertEqual(refreshed["status"], "unchanged")
        self.assertEqual(NoteSyncRevision.objects.count(), 0)
        self.assertEqual(path.read_bytes(), source_before)

    def test_unknown_resolution_action_is_rejected(self):
        with self.assertRaisesMessage(ValueError, "Unknown conflict resolution action"):
            self.resolve("overwrite_everything")

    def test_unmatched_refresh_does_not_create_annotation_or_binding(self):
        result = self.refresh()

        self.assertEqual(result["status"], "unmatched")
        self.assertFalse(Annotations.objects.filter(document=self.document).exists())
        self.assertFalse(NoteSyncBinding.objects.filter(document=self.document).exists())

    def test_sync_state_exposes_marker_and_binding(self):
        unlinked = get_document_sync_state(self.document)
        self.write_note("Body")
        self.refresh()
        linked = get_document_sync_state(self.document)

        self.assertEqual(unlinked["status"], "unlinked")
        self.assertEqual(unlinked["marker"], f"#rm:{self.document.note_sync_code}")
        self.assertEqual(linked["status"], "linked")
        self.assertTrue(linked["file_path"].endswith("paper.md"))

    def test_global_refresh_imports_known_code_and_reports_unknown_code(self):
        self.write_note("Known")
        unknown = self.root / "unknown.md"
        unknown.write_text("#rm:UNKNOWN123\nUnknown", encoding="utf-8")

        with patch(
            "api.note_sync.load_note_sync_directories",
            return_value=([str(self.root)], []),
        ):
            result = refresh_all_notes()

        self.assertEqual(result["counts"], {"imported": 1, "unknown_code": 1})
        imported = next(item for item in result["results"] if item["status"] == "imported")
        self.assertNotIn("notepad", imported)
        self.assertEqual(unknown.read_text(encoding="utf-8"), "#rm:UNKNOWN123\nUnknown")

    def test_global_refresh_reports_a_missing_previously_linked_file(self):
        path = self.write_note("Known")
        self.refresh()
        path.unlink()

        with patch(
            "api.note_sync.load_note_sync_directories",
            return_value=([str(self.root)], []),
        ):
            result = refresh_all_notes()

        self.assertEqual(result["counts"], {"unmatched": 1})
        self.assertIn("previously linked", result["results"][0]["message"])

    def test_directory_validation_normalizes_and_deduplicates(self):
        directories, errors = sanitize_note_sync_directories(
            [str(self.root), str(self.root), ""]
        )
        self.assertEqual(directories, [str(self.root.resolve())])
        self.assertEqual(errors, [])

    def test_directory_validation_rejects_files_and_relative_paths(self):
        file_path = self.root / "note.md"
        file_path.write_text("Body", encoding="utf-8")

        directories, errors = sanitize_note_sync_directories(
            [str(file_path), "relative/notes"]
        )

        self.assertEqual(directories, [])
        self.assertEqual(len(errors), 2)

    @patch("api.views.refresh_document_note")
    def test_individual_refresh_endpoint(self, refresh):
        refresh.return_value = {
            "document_id": self.document.id,
            "status": "unchanged",
        }
        response = self.client.post(
            reverse("document-note-sync", kwargs={"pk": self.document.id}),
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        refresh.assert_called_once_with(self.document)

    @patch("api.views.refresh_all_notes", return_value={"counts": {}, "results": []})
    def test_global_refresh_endpoint(self, refresh):
        response = self.client.post(reverse("note-sync-refresh-all"), {}, format="json")
        self.assertEqual(response.status_code, 200)
        refresh.assert_called_once_with()

    def test_sync_endpoints_return_not_found_for_unknown_paper(self):
        refresh = self.client.post(
            reverse("document-note-sync", kwargs={"pk": 999999}),
            {},
            format="json",
        )
        resolve = self.client.post(
            reverse("document-note-sync-resolve", kwargs={"pk": 999999}),
            {"action": "keep_both"},
            format="json",
        )
        self.assertEqual(refresh.status_code, 404)
        self.assertEqual(resolve.status_code, 404)

    def test_resolve_endpoint_rejects_unknown_action(self):
        response = self.client.post(
            reverse("document-note-sync-resolve", kwargs={"pk": self.document.id}),
            {"action": "bad"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
