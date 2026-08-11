from datetime import date

from django.test import SimpleTestCase

from api.apps import _parse_last_import_date
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
