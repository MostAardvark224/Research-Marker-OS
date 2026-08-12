from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from api.models import Annotations, ChatLogs, Document


class AnnotationAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.document = Document.objects.create(title="Paper", file="documents/paper.pdf")

    def test_annotation_post_creates_then_upserts_one_record_per_document(self):
        first = self.client.post(
            reverse("annotations-list"),
            {"document": self.document.id, "notepad": "First note", "highlight_data": []},
            format="json",
        )
        second = self.client.post(
            reverse("annotations-list"),
            {"document": self.document.id, "notepad": "Updated note", "sticky_note_data": []},
            format="json",
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(Annotations.objects.count(), 1)
        self.assertEqual(Annotations.objects.get().notepad, "Updated note")

    def test_annotation_detail_uses_document_id_as_lookup(self):
        annotation = Annotations.objects.create(document=self.document, notepad="Note")

        response = self.client.get(
            reverse("annotations-detail", kwargs={"document": self.document.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], annotation.id)

    def test_search_notes_groups_annotations_by_document(self):
        Annotations.objects.create(
            document=self.document,
            notepad="Searchable note",
            highlight_data=[{"page": 1, "text": "Finding"}],
        )

        response = self.client.get(reverse("search-notes"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["title"], "Paper")
        self.assertEqual(response.data[0]["doc_id"], self.document.id)
        self.assertEqual(response.data[0]["annotations"]["notepad"], "Searchable note")

    def test_post_for_missing_document_returns_client_error(self):
        response = self.client.post(
            reverse("annotations-list"), {"document": 999999, "notepad": "Note"}, format="json"
        )
        self.assertIn(response.status_code, {400, 404})


class ChatLogAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_chatlog_crud(self):
        created = self.client.post(
            reverse("chatlogs-list"),
            {"name": "Discussion", "content": [{"role": "user", "content": "Hi"}]},
            format="json",
        )
        self.assertEqual(created.status_code, 201)

        detail_url = reverse("chatlogs-detail", kwargs={"pk": created.data["id"]})
        updated = self.client.patch(detail_url, {"name": "Renamed"}, format="json")
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.data["name"], "Renamed")

        listing = self.client.get(reverse("chatlogs-list"))
        self.assertEqual(len(listing.data), 1)

        deleted = self.client.delete(detail_url)
        self.assertEqual(deleted.status_code, 204)
        self.assertFalse(ChatLogs.objects.exists())
