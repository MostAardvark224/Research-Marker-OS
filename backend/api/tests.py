from datetime import date

from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from api.models import Document

from api.apps import _parse_last_import_date
from api.arxiv import parse_arxiv_id
from api.scholar_inbox import (
    _normalize_amount,
    _normalize_gmail_app_password,
    _truncate_title,
)


class ScholarInboxAmountTests(SimpleTestCase):
    def test_normalize_amount_positive_int(self):
        self.assertEqual(_normalize_amount(5), 5)

    def test_normalize_amount_digit_string(self):
        self.assertEqual(_normalize_amount("3"), 3)

    def test_normalize_amount_all_variants(self):
        for value in (None, "all", "All", "ALL", ""):
            self.assertIsNone(_normalize_amount(value))

    def test_normalize_amount_zero_is_disabled(self):
        self.assertIsNone(_normalize_amount(0))
        self.assertIsNone(_normalize_amount("0"))

    def test_normalize_amount_invalid_values(self):
        self.assertIsNone(_normalize_amount("five"))
        self.assertIsNone(_normalize_amount([]))

    def test_normalize_gmail_app_password_strips_spaces(self):
        self.assertEqual(
            _normalize_gmail_app_password("abcd efgh ijkl mnop"),
            "abcdefghijklmnop",
        )

    def test_truncate_title(self):
        long_title = "A" * 300
        truncated = _truncate_title(long_title)
        self.assertEqual(len(truncated), 255)
        self.assertTrue(truncated.endswith("…"))

class ScholarInboxDateTests(SimpleTestCase):
    def test_parse_last_import_date_valid(self):
        self.assertEqual(_parse_last_import_date("2026-07-08"), date(2026, 7, 8))

    def test_parse_last_import_date_nullish(self):
        for value in (None, "", "null"):
            self.assertIsNone(_parse_last_import_date(value))

    def test_parse_last_import_date_invalid(self):
        self.assertIsNone(_parse_last_import_date("not-a-date"))


class ArxivIdParseTests(SimpleTestCase):
    def test_parse_abs_url(self):
        self.assertEqual(
            parse_arxiv_id("https://arxiv.org/abs/2301.12345"),
            "2301.12345",
        )

    def test_parse_pdf_url(self):
        self.assertEqual(
            parse_arxiv_id("https://arxiv.org/pdf/2301.12345.pdf"),
            "2301.12345",
        )

    def test_parse_versioned_id(self):
        self.assertEqual(
            parse_arxiv_id("https://arxiv.org/abs/2301.12345v2"),
            "2301.12345v2",
        )

    def test_parse_bare_id(self):
        self.assertEqual(parse_arxiv_id("2301.12345"), "2301.12345")

    def test_parse_legacy_id(self):
        self.assertEqual(parse_arxiv_id("cs/9901001"), "cs/9901001")

    def test_parse_invalid(self):
        self.assertIsNone(parse_arxiv_id("https://example.com/paper"))


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
