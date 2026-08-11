from django.test import TestCase
from rest_framework.response import Response
from rest_framework.test import APIClient

from api.models import Document


class DocumentReadStatusTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.document = Document.objects.create(
            title="Unread paper",
            file="documents/unread-paper.pdf",
        )

    def test_document_is_unread_by_default(self):
        response = self.client.get(f"/api/documents/{self.document.id}/")

        self.assertEqual(response.status_code, 200)
        assert isinstance(response, Response)
        assert response.data is not None
        self.assertIs(response.data["is_read"], False)

    def test_document_can_be_marked_as_read(self):
        response = self.client.patch(
            f"/api/documents/{self.document.id}/",
            {"is_read": True},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.document.refresh_from_db()
        self.assertIs(self.document.is_read, True)
