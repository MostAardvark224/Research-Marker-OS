import tempfile
from pathlib import Path
from unittest.mock import patch

import fitz
from django.core.files import File
from django.test import TestCase, override_settings

from api.models import Document
from api.table_of_contents import (
    cancel_document_table_of_contents,
    extract_document_table_of_contents,
    scrape_document_table_of_contents,
)


def _write_pdf(path: Path, build) -> None:
    pdf = fitz.open()
    build(pdf)
    pdf.save(path)
    pdf.close()


class TableOfContentsScraperTests(TestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.media.name)
        self.media_override.enable()

    def tearDown(self):
        self.media_override.disable()
        self.media.cleanup()

    def _create_document(self, filename: str, build, **values) -> Document:
        source_path = Path(self.media.name) / filename
        _write_pdf(source_path, build)
        with source_path.open("rb") as source:
            document = Document.objects.create(
                title=filename,
                file=File(source, name=filename),
                toc_status=Document.TocStatus.QUEUED,
                **values,
            )
        return document

    def test_scraper_persists_nested_embedded_outline_with_pdf_pages(self):
        document = self._create_document(
            "book.pdf",
            lambda pdf: (
                [pdf.new_page() for _ in range(5)],
                pdf.set_toc(
                    [
                        [1, "Chapter 1", 2],
                        [2, "Section 1.1", 4],
                        [1, "Chapter 2", 5],
                    ]
                ),
            ),
        )

        scrape_document_table_of_contents(document.id)
        document.refresh_from_db()

        self.assertEqual(document.toc_status, Document.TocStatus.SUCCEEDED)
        self.assertEqual(document.toc_source, "embedded")
        self.assertEqual(document.page_count, 5)
        self.assertEqual(document.toc_progress, 100)
        self.assertEqual(document.toc_data[0]["page"], 2)
        self.assertEqual(document.toc_data[0]["children"][0]["page"], 4)

    def test_scraper_reads_printed_contents_when_outline_is_missing(self):
        def build(pdf):
            toc_page = pdf.new_page()
            toc_page.insert_text((72, 72), "Table of Contents", fontsize=16)
            toc_page.insert_text((72, 110), "Chapter 1  Introduction  3", fontsize=11)
            toc_page.insert_text((92, 128), "1.1  Background  4", fontsize=11)
            toc_page.insert_text((72, 146), "Chapter 2  Methods  5", fontsize=11)
            pdf.new_page()
            intro = pdf.new_page()
            intro.insert_text((72, 72), "Chapter 1 Introduction", fontsize=16)
            background = pdf.new_page()
            background.insert_text((72, 72), "1.1 Background", fontsize=14)
            methods = pdf.new_page()
            methods.insert_text((72, 72), "Chapter 2 Methods", fontsize=16)

        source_path = Path(self.media.name) / "printed.pdf"
        _write_pdf(source_path, build)
        items, page_count, source = extract_document_table_of_contents(source_path)

        self.assertEqual(page_count, 5)
        self.assertEqual(source, "printed")
        self.assertEqual([item["title"] for item in items], ["Chapter 1 Introduction", "Chapter 2 Methods"])
        self.assertEqual(items[0]["page"], 3)
        self.assertEqual(items[0]["children"][0]["title"], "1.1 Background")
        self.assertEqual(items[0]["children"][0]["page"], 4)
        self.assertEqual(items[1]["page"], 5)

    def test_scraper_prefers_printed_contents_over_generic_outline(self):
        def build(pdf):
            toc_page = pdf.new_page()
            toc_page.insert_text((72, 72), "Contents", fontsize=16)
            toc_page.insert_text((72, 110), "Chapter 1  Introduction  2", fontsize=11)
            toc_page.insert_text((72, 128), "Chapter 2  Methods  3", fontsize=11)
            toc_page.insert_text((72, 146), "Chapter 3  Results  4", fontsize=11)
            intro = pdf.new_page()
            intro.insert_text((72, 72), "Chapter 1 Introduction", fontsize=16)
            methods = pdf.new_page()
            methods.insert_text((72, 72), "Chapter 2 Methods", fontsize=16)
            results = pdf.new_page()
            results.insert_text((72, 72), "Chapter 3 Results", fontsize=16)
            pdf.set_toc([[1, "Page 1", 1], [1, "Page 2", 1], [1, "Page 3", 1]])

        source_path = Path(self.media.name) / "generic.pdf"
        _write_pdf(source_path, build)
        items, _page_count, source = extract_document_table_of_contents(source_path)

        self.assertEqual(source, "printed")
        self.assertEqual(
            [item["title"] for item in items],
            ["Chapter 1 Introduction", "Chapter 2 Methods", "Chapter 3 Results"],
        )

    def test_scraper_reads_wrapped_titles_and_two_column_contents(self):
        def build(pdf):
            toc_page = pdf.new_page()
            toc_page.insert_text((72, 60), "Contents", fontsize=16)
            toc_page.insert_text((72, 100), "A Long Chapter Title", fontsize=11)
            toc_page.insert_text((92, 118), "Continued ........ 3", fontsize=11)
            toc_page.insert_text((72, 145), "Methods ........ 4", fontsize=11)
            toc_page.insert_text((320, 100), "Results ........ 5", fontsize=11)
            toc_page.insert_text((320, 145), "Discussion ........ 6", fontsize=11)
            pdf.new_page()
            for title in (
                "A Long Chapter Title Continued",
                "Methods",
                "Results",
                "Discussion",
            ):
                page = pdf.new_page()
                page.insert_text((72, 72), title, fontsize=16)

        source_path = Path(self.media.name) / "columns.pdf"
        _write_pdf(source_path, build)
        items, _page_count, source = extract_document_table_of_contents(source_path)

        self.assertEqual(source, "printed")
        self.assertEqual(
            [item["title"] for item in items],
            [
                "A Long Chapter Title Continued",
                "Methods",
                "Results",
                "Discussion",
            ],
        )
        self.assertEqual([item["page"] for item in items], [3, 4, 5, 6])

    def test_scraper_infers_outline_from_visible_document_headings(self):
        def build(pdf):
            sections = (
                ("Introduction", "This is the opening body text for the research paper."),
                ("Methods", "This section describes the complete experimental procedure."),
                ("Results", "This section presents the measured experimental outcomes."),
                ("Discussion", "This section discusses the meaning of the observed results."),
            )
            for heading, body in sections:
                page = pdf.new_page()
                page.insert_text((72, 72), heading, fontsize=15)
                page.insert_text((72, 110), body, fontsize=10)

        source_path = Path(self.media.name) / "inferred.pdf"
        _write_pdf(source_path, build)
        items, _page_count, source = extract_document_table_of_contents(source_path)

        self.assertEqual(source, "inferred")
        self.assertEqual(
            [item["title"] for item in items],
            ["Introduction", "Methods", "Results", "Discussion"],
        )
        self.assertEqual([item["page"] for item in items], [1, 2, 3, 4])

    def test_scraper_maps_roman_front_matter_and_reset_page_numbers(self):
        def build(pdf):
            toc_page = pdf.new_page()
            toc_page.insert_text((72, 60), "Table of Contents", fontsize=16)
            toc_page.insert_text((72, 100), "Preface ........ iv", fontsize=11)
            toc_page.insert_text((72, 120), "1 Introduction ........ 1", fontsize=11)
            toc_page.insert_text((72, 140), "2 Methods ........ 2", fontsize=11)
            toc_page.insert_text((72, 160), "3 Results ........ 3", fontsize=11)
            for title in ("Preface", "1 Introduction", "2 Methods", "3 Results"):
                page = pdf.new_page()
                page.insert_text((72, 72), title, fontsize=16)

        source_path = Path(self.media.name) / "roman-pages.pdf"
        _write_pdf(source_path, build)
        items, _page_count, source = extract_document_table_of_contents(source_path)

        self.assertEqual(source, "printed")
        self.assertEqual([item["page"] for item in items], [2, 3, 4, 5])

    def test_scraper_splits_combined_entries_and_restores_missing_chapters(self):
        def build(pdf):
            toc_page = pdf.new_page()
            toc_page.insert_text((72, 60), "Contents", fontsize=16)
            toc_page.insert_text((72, 100), "Introduction Methods ........ 1", fontsize=11)
            toc_page.insert_text((72, 120), "Results ........ 3", fontsize=11)
            toc_page.insert_text((72, 140), "Conclusion ........ 5", fontsize=11)
            pdf.new_page()
            for heading in (
                "Introduction",
                "Methods",
                "Results",
                "Discussion",
                "Conclusion",
            ):
                page = pdf.new_page()
                page.insert_text((72, 72), heading, fontsize=15)
                page.insert_text(
                    (72, 110),
                    "Long body text establishes the normal font size for this section.",
                    fontsize=10,
                )

        source_path = Path(self.media.name) / "combined-and-missing.pdf"
        _write_pdf(source_path, build)
        items, _page_count, source = extract_document_table_of_contents(source_path)

        self.assertEqual(source, "hybrid")
        self.assertEqual(
            [item["title"] for item in items],
            ["Introduction", "Methods", "Results", "Discussion", "Conclusion"],
        )
        self.assertEqual([item["page"] for item in items], [3, 4, 5, 6, 7])

    def test_large_valid_printed_toc_skips_full_document_heading_scan(self):
        def build(pdf):
            toc_page = pdf.new_page()
            toc_page.insert_text((72, 45), "Contents", fontsize=16)
            for index in range(15):
                toc_page.insert_text(
                    (72, 75 + index * 18),
                    f"Chapter {index + 1} ........ {index + 2}",
                    fontsize=10,
                )
            for _index in range(15):
                pdf.new_page()

        source_path = Path(self.media.name) / "large-valid-toc.pdf"
        _write_pdf(source_path, build)
        with patch("api.table_of_contents._infer_document_outline") as infer:
            items, _page_count, source = extract_document_table_of_contents(source_path)

        infer.assert_not_called()
        self.assertEqual(source, "printed")
        self.assertEqual(len(items), 15)

    def test_ocr_contents_without_page_numbers_uses_body_heading_matches(self):
        def build(pdf):
            toc_page = pdf.new_page()
            toc_page.insert_text((72, 45), "Comtemts", fontsize=16)
            toc_page.insert_text((72, 75), "Introduction", fontsize=10)
            toc_page.insert_text((72, 95), "1. First Languages", fontsize=10)
            toc_page.insert_text((72, 115), "2. A Chapter with a Wrapped", fontsize=10)
            toc_page.insert_text((92, 132), "Title", fontsize=10)
            toc_page.insert_text((72, 152), "Part I: History", fontsize=10)
            pdf.new_page()
            for heading in (
                "Introduction",
                "1. First Languages",
                "2. A Chapter with a Wrapped Title",
                "Part I: History",
            ):
                page = pdf.new_page()
                page.insert_text((72, 72), heading, fontsize=15)

        source_path = Path(self.media.name) / "ocr-no-page-numbers.pdf"
        _write_pdf(source_path, build)
        items, _page_count, source = extract_document_table_of_contents(source_path)

        self.assertEqual(source, "printed")
        self.assertEqual(
            [item["title"] for item in items],
            [
                "Introduction",
                "1. First Languages",
                "2. A Chapter with a Wrapped Title",
                "Part I: History",
            ],
        )
        self.assertEqual([item["page"] for item in items], [3, 4, 5, 6])

    def test_cancelled_scrape_does_not_overwrite_existing_outline(self):
        document = Document.objects.create(
            title="Book",
            file="documents/book.pdf",
            toc_status=Document.TocStatus.PROCESSING,
            toc_data=[{"id": "manual", "title": "Manual chapter", "page": 1, "children": []}],
        )

        cancel_document_table_of_contents(document, "Cancelled by user.")
        scrape_document_table_of_contents(document.id)
        document.refresh_from_db()

        self.assertEqual(document.toc_status, Document.TocStatus.CANCELLED)
        self.assertEqual(document.toc_data[0]["title"], "Manual chapter")
        self.assertEqual(document.toc_progress_message, "Cancelled by user.")
