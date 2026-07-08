from datetime import date

from django.test import SimpleTestCase

from api.apps import _parse_last_import_date
from api.arxiv import parse_arxiv_id
from api.scholar_inbox import _normalize_amount


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
