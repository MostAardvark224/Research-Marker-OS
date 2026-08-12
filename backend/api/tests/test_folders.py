from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from api.models import Document, Folder


class FolderAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_folder_crud_and_nested_serialization(self):
        created = self.client.post(reverse("folders-list"), {"name": "Parent"}, format="json")
        self.assertEqual(created.status_code, 201)
        parent_id = created.data["id"]

        child = self.client.post(
            reverse("folders-list"), {"name": "Child", "parent": parent_id}, format="json"
        )
        self.assertEqual(child.status_code, 201)

        detail = self.client.get(reverse("folders-detail", kwargs={"pk": parent_id}))
        self.assertEqual(detail.data["subfolders"][0]["name"], "Child")

        renamed = self.client.patch(
            reverse("folders-detail", kwargs={"pk": child.data["id"]}),
            {"name": "Renamed"},
            format="json",
        )
        self.assertEqual(renamed.status_code, 200)
        deleted = self.client.delete(reverse("folders-detail", kwargs={"pk": child.data["id"]}))
        self.assertEqual(deleted.status_code, 204)

    def test_duplicate_name_at_same_level_is_rejected_but_allowed_elsewhere(self):
        first_parent = Folder.objects.create(name="First")
        second_parent = Folder.objects.create(name="Second")
        Folder.objects.create(name="Notes", parent=first_parent)

        duplicate = self.client.post(
            reverse("folders-list"), {"name": "Notes", "parent": first_parent.id}, format="json"
        )
        allowed = self.client.post(
            reverse("folders-list"), {"name": "Notes", "parent": second_parent.id}, format="json"
        )

        self.assertEqual(duplicate.status_code, 400)
        self.assertTrue("name" in duplicate.data or "non_field_errors" in duplicate.data)
        self.assertEqual(allowed.status_code, 201)

    def test_reorder_documents_updates_order_only_within_folder(self):
        folder = Folder.objects.create(name="Folder")
        first = Document.objects.create(title="First", file="documents/first.pdf", folder=folder)
        second = Document.objects.create(title="Second", file="documents/second.pdf", folder=folder)

        response = self.client.post(
            reverse("documents-reorder"),
            {"folder_id": folder.id, "document_ids": [second.id, first.id]},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual((second.sort_order, first.sort_order), (0, 1))

    def test_reorder_documents_rejects_empty_or_cross_folder_ids(self):
        folder = Folder.objects.create(name="Folder")
        other = Folder.objects.create(name="Other")
        document = Document.objects.create(title="Paper", file="documents/paper.pdf", folder=other)

        empty = self.client.post(
            reverse("documents-reorder"), {"folder_id": folder.id, "document_ids": []}, format="json"
        )
        wrong_folder = self.client.post(
            reverse("documents-reorder"),
            {"folder_id": folder.id, "document_ids": [document.id]},
            format="json",
        )

        self.assertEqual(empty.status_code, 400)
        self.assertEqual(wrong_folder.status_code, 400)

    def test_reorder_folders_updates_siblings_and_rejects_other_parent(self):
        parent = Folder.objects.create(name="Parent")
        first = Folder.objects.create(name="First", parent=parent)
        second = Folder.objects.create(name="Second", parent=parent)
        outsider = Folder.objects.create(name="Outside")

        response = self.client.post(
            reverse("folders-reorder"),
            {"parent_id": parent.id, "folder_ids": [second.id, first.id]},
            format="json",
        )
        invalid = self.client.post(
            reverse("folders-reorder"),
            {"parent_id": parent.id, "folder_ids": [outsider.id]},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual((second.sort_order, first.sort_order), (0, 1))
        self.assertEqual(invalid.status_code, 400)
