import json
import urllib.error
from datetime import date
from unittest.mock import patch

from django.test import SimpleTestCase

from api.apps import _parse_last_import_date
from api.scholar_inbox import (
    ScholarInboxError,
    _api_paper_limit,
    _arxiv_pdf_url,
    _normalize_amount,
    _truncate_title,
    fetch_scholar_inbox_papers,
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

    def test_api_limit_caps_all_and_large_requests_at_api_maximum(self):
        self.assertEqual(_api_paper_limit("All"), 100)
        self.assertEqual(_api_paper_limit(500), 100)
        self.assertEqual(_api_paper_limit(5), 5)

    def test_truncate_title(self):
        long_title = "A" * 300
        truncated = _truncate_title(long_title)
        self.assertEqual(len(truncated), 255)
        self.assertTrue(truncated.endswith("…"))


class ScholarInboxAPIFetchTests(SimpleTestCase):
    def test_arxiv_url_is_converted_directly_to_pdf(self):
        self.assertEqual(
            _arxiv_pdf_url("https://arxiv.org/abs/2608.12345v2"),
            ("2608.12345v2", "https://arxiv.org/pdf/2608.12345v2.pdf"),
        )
        self.assertIsNone(_arxiv_pdf_url("https://example.com/paper"))

    def test_missing_api_key_is_actionable(self):
        with self.assertRaises(ScholarInboxError) as raised:
            fetch_scholar_inbox_papers({}, 5)

        self.assertEqual(raised.exception.code, "credentials_missing")
        self.assertEqual(raised.exception.http_status, 400)

    @patch("api.scholar_inbox.urllib.request.urlopen")
    def test_fetch_uses_bearer_key_and_digest_url_field(self, urlopen):
        payload = {
            "success": True,
            "papers": [
                {
                    "paper_id": 1,
                    "title": "  A   useful paper  ",
                    "url": "https://arxiv.org/abs/2608.12345",
                    "arxiv_id": "2608.12345",
                },
                {
                    "paper_id": 2,
                    "title": "Not on arXiv",
                    "url": "https://example.com/paper",
                },
            ],
        }
        urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(
            payload
        ).encode()

        result = fetch_scholar_inbox_papers(
            {"SCHOLAR_INBOX_API_KEY": "test-key"}, 5
        )

        request = urlopen.call_args.args[0]
        self.assertEqual(
            request.full_url,
            "https://api.scholar-inbox.com/v1/digest?top_k=5",
        )
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
        self.assertEqual(result["titles_found"], 2)
        self.assertEqual(result["unmatched_titles"], ["Not on arXiv"])
        self.assertEqual(
            result["papers"],
            [
                {
                    "id": "2608.12345",
                    "title": "A useful paper",
                    "pdf_url": "https://arxiv.org/pdf/2608.12345.pdf",
                    "source_url": "https://arxiv.org/abs/2608.12345",
                }
            ],
        )

    @patch("api.scholar_inbox.urllib.request.urlopen")
    def test_empty_digest_is_not_found(self, urlopen):
        urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(
            {"success": True, "papers": []}
        ).encode()

        result = fetch_scholar_inbox_papers(
            {"SCHOLAR_INBOX_API_KEY": "test-key"}, "All"
        )

        self.assertFalse(result["digest_found"])
        self.assertEqual(result["titles_found"], 0)
        request = urlopen.call_args.args[0]
        self.assertTrue(request.full_url.endswith("top_k=100"))

    @patch("api.scholar_inbox.urllib.request.urlopen")
    def test_rejected_api_key_has_actionable_error(self, urlopen):
        urlopen.side_effect = urllib.error.HTTPError(
            "https://api.scholar-inbox.com/v1/digest",
            401,
            "Unauthorized",
            {},
            None,
        )

        with self.assertRaises(ScholarInboxError) as raised:
            fetch_scholar_inbox_papers(
                {"SCHOLAR_INBOX_API_KEY": "invalid-key"}, 5
            )

        self.assertEqual(raised.exception.code, "api_auth_failed")
        self.assertEqual(raised.exception.http_status, 401)


class ScholarInboxDateTests(SimpleTestCase):
    def test_parse_last_import_date_valid(self):
        self.assertEqual(_parse_last_import_date("2026-07-08"), date(2026, 7, 8))

    def test_parse_last_import_date_nullish(self):
        for value in (None, "", "null"):
            self.assertIsNone(_parse_last_import_date(value))

    def test_parse_last_import_date_invalid(self):
        self.assertIsNone(_parse_last_import_date("not-a-date"))
