from unittest.mock import patch

from django.test import SimpleTestCase

from api.arxiv import (
    _fetch_arxiv_metadata_cached,
    _metadata_from_abs_page,
    fetch_arxiv_metadata,
    parse_arxiv_id,
)


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

    def test_parse_extensionless_versioned_pdf_url(self):
        self.assertEqual(
            parse_arxiv_id("https://arxiv.org/pdf/2609.28769v1"),
            "2609.28769v1",
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


class ArxivMetadataTests(SimpleTestCase):
    def tearDown(self):
        _fetch_arxiv_metadata_cached.cache_clear()

    def test_extracts_metadata_from_abstract_page(self):
        page = b"""
            <html><head>
              <meta name="citation_title" content="  A Paper &amp; Its Title  ">
              <meta name="citation_pdf_url" content="https://arxiv.org/pdf/2609.28769v1">
            </head></html>
        """

        self.assertEqual(
            _metadata_from_abs_page("2609.28769v1", page),
            {
                "arxiv_id": "2609.28769v1",
                "title": "A Paper & Its Title",
                "pdf_url": "https://arxiv.org/pdf/2609.28769v1",
            },
        )

    @patch("api.arxiv._fetch_arxiv_abs_metadata")
    @patch("api.arxiv._fetch_arxiv_api_metadata")
    def test_falls_back_to_abstract_page_when_api_fails(self, api_fetch, abs_fetch):
        api_fetch.side_effect = RuntimeError("HTTP 406")
        abs_fetch.return_value = {
            "arxiv_id": "2609.28769v1",
            "title": "Xtrace",
            "pdf_url": "https://arxiv.org/pdf/2609.28769v1",
        }

        self.assertEqual(fetch_arxiv_metadata("2609.28769v1")["title"], "Xtrace")
        abs_fetch.assert_called_once_with("2609.28769v1")

    @patch("api.arxiv._fetch_arxiv_api_metadata")
    def test_reuses_metadata_for_lookup_then_import(self, api_fetch):
        api_fetch.return_value = {
            "arxiv_id": "2609.28769v1",
            "title": "Xtrace",
            "pdf_url": "https://arxiv.org/pdf/2609.28769v1",
        }

        fetch_arxiv_metadata("2609.28769v1")
        fetch_arxiv_metadata("2609.28769v1")

        api_fetch.assert_called_once_with("2609.28769v1")
