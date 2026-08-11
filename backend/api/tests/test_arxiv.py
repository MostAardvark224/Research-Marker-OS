from django.test import SimpleTestCase

from api.arxiv import parse_arxiv_id


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
