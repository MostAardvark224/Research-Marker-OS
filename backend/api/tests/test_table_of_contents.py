import tempfile
from pathlib import Path

import fitz
from django.core.files import File
from django.test import TestCase, override_settings

from api.models import Document
from api.table_of_contents import scrape_document_table_of_contents


class TableOfContentsScraperTests(TestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.media.name)
        self.media_override.enable()

    def tearDown(self):
        self.media_override.disable()
        self.media.cleanup()

    def test_scraper_persists_nested_embedded_outline_with_pdf_pages(self):
        source_path = Path(self.media.name) / "source.pdf"
        pdf = fitz.open()
        for _ in range(5):
            pdf.new_page()
        pdf.set_toc(
            [
                [1, "Chapter 1", 2],
                [2, "Section 1.1", 4],
                [1, "Chapter 2", 5],
            ]
        )
        pdf.save(source_path)
        pdf.close()

        with source_path.open("rb") as source:
            document = Document.objects.create(
                title="Book",
                file=File(source, name="book.pdf"),
                toc_status=Document.TocStatus.QUEUED,
            )

        scrape_document_table_of_contents(document.id)
        document.refresh_from_db()

        self.assertEqual(document.toc_status, Document.TocStatus.SUCCEEDED)
        self.assertEqual(document.toc_source, "embedded")
        self.assertEqual(document.page_count, 5)
        self.assertEqual(document.toc_data[0]["page"], 2)
        self.assertEqual(document.toc_data[0]["children"][0]["page"], 4)
