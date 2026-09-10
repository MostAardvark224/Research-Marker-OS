from __future__ import annotations

import re
import statistics
import time
import uuid
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import fitz
from django.utils import timezone

from api.models import Document

MAX_TOC_DEPTH = 12
MAX_TOC_ITEMS = 1000
MAX_TOC_TITLE_LENGTH = 500
MAX_PRINTED_TOC_SCAN_PAGES = 40
MAX_OCR_TOC_SCAN_PAGES = 8
MAX_OCR_TOC_SECONDS = 12.0
MIN_PRINTED_TOC_ENTRIES = 3
MIN_INFERRED_TOC_ENTRIES = 3
MAX_RECONCILIATION_TOC_ENTRIES = 12
MAX_DETAILED_INFERENCE_PAGES = 200
MAX_FAST_INFERRED_TOC_ITEMS = 250
TOC_TASK_FUNCTION = "api.table_of_contents.scrape_document_table_of_contents"
TOC_QUEUE_UPDATE_FIELDS = [
    "toc_status",
    "toc_error",
    "toc_started_at",
    "toc_completed_at",
    "toc_task_id",
    "toc_progress",
    "toc_progress_message",
]

ProgressCallback = Callable[[int, str], bool]

_TOC_HEADING_RE = re.compile(
    r"^(table\s+of\s+contents|contents|inhaltsverzeichnis|sommaire|"
    r"indice(?:\s+generale)?|índice(?:\s+de\s+contenidos)?)$",
    re.IGNORECASE,
)
_STOP_HEADING_RE = re.compile(
    r"^(list of (?:figures|tables|illustrations|maps)|preface|acknowledgements?)$",
    re.IGNORECASE,
)
_LEADER_PAGE_RE = re.compile(
    r"^(?P<title>.+?)(?:\s*(?:\.{2,}|[·•.](?:\s*[·•.]){2,})\s*|\s{2,})\s*"
    r"(?P<page>\d{1,4}|[ivxlcdm]{1,8})\s*$",
    re.IGNORECASE,
)
_NUMBERED_PAGE_RE = re.compile(
    r"^(?P<title>(?:(?:\d+\.)+\d*|\d+|[IVXLCDM]+\.)\s+\S.*)\s+"
    r"(?P<page>\d{1,4}|[ivxlcdm]{1,8})\s*$",
    re.IGNORECASE,
)
_CHAPTER_PAGE_RE = re.compile(
    r"^(?P<title>(?:chapter|part|appendix|section)\s+\S.*)\s+"
    r"(?P<page>\d{1,4}|[ivxlcdm]{1,8})\s*$",
    re.IGNORECASE,
)
_LOOSE_PAGE_RE = re.compile(
    r"^(?P<title>\S(?:.*\S)?)\s+(?P<page>\d{1,4}|[ivxlcdm]{1,8})\s*$",
    re.IGNORECASE,
)
_PAGE_ONLY_RE = re.compile(r"^(?:[.·•]\s*)*(\d{1,4}|[ivxlcdm]{1,8})$", re.IGNORECASE)
_NUMBER_PREFIX_RE = re.compile(
    r"^(?P<number>(?:\d+\.)+\d*|\d+|[IVXLCDM]+\.?|[A-Z]\.)\s+"
)
_GENERIC_TITLE_RE = re.compile(r"^(?:page\s*)?\d+$", re.IGNORECASE)
_CHAPTER_PREFIX_RE = re.compile(r"^(chapter|part|appendix|section)\b", re.IGNORECASE)
_STRUCTURAL_HEADING_RE = re.compile(
    r"^(abstract|introduction|background|related work|literature review|"
    r"materials and methods|methods?|methodology|experimental setup|experiments?|"
    r"results?|findings|analysis|discussion|conclusions?|limitations|future work|"
    r"references|bibliography|acknowledgements?|appendix|supplementary materials?)$",
    re.IGNORECASE,
)
_SECTION_NUMBER_RE = re.compile(
    r"^(?P<number>\d+(?:\.\d+)*)(?:[.)])?\s+(?P<title>\S.*)$"
)
_REJECTED_HEADING_RE = re.compile(
    r"^(fig(?:ure)?|table|equation|algorithm)\s+\d+|"
    r"^(https?://|www\.|doi\b)",
    re.IGNORECASE,
)
_ENTRY_MARKER_RE = re.compile(
    r"\b(?:chapter|part|appendix|section)\s+[a-z0-9]+|"
    r"\b(?:introduction|methods?|results?|discussion|conclusions?)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PageLine:
    text: str
    x0: float
    x1: float
    y0: float
    y1: float
    size: float
    bold: bool = False


@dataclass(frozen=True)
class InferredHeading:
    title: str
    page: int
    level: int
    size: float


class TocCancelled(Exception):
    """Raised when a scrape should stop because the user cancelled it."""


def prepare_table_of_contents_queue(document: Document) -> None:
    document.toc_status = Document.TocStatus.QUEUED
    document.toc_error = ""
    document.toc_started_at = None
    document.toc_completed_at = None
    document.toc_task_id = ""
    document.toc_progress = 0
    document.toc_progress_message = "Waiting for the background worker…"


def _report_progress(callback: ProgressCallback | None, percent: int, message: str) -> None:
    if callback is None:
        return
    if callback(max(0, min(100, percent)), message) is False:
        raise TocCancelled()


def _flatten_toc(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for item in items:
        flattened.append(item)
        flattened.extend(_flatten_toc(item.get("children") or []))
    return flattened


def _build_toc_tree(entries: list[list[Any]], page_count: int) -> list[dict[str, Any]]:
    roots: list[dict[str, Any]] = []
    parents: list[dict[str, Any]] = []

    for index, entry in enumerate(entries):
        if len(entry) < 3:
            continue
        try:
            requested_level = max(1, int(entry[0]))
            page = int(entry[2])
        except (TypeError, ValueError):
            continue

        title = str(entry[1] or "").strip()
        if not title or page < 1 or page > page_count:
            continue

        level = min(requested_level, len(parents) + 1, MAX_TOC_DEPTH)
        node = {
            "id": f"toc-{index}",
            "title": title[:MAX_TOC_TITLE_LENGTH],
            "page": page,
            "children": [],
        }

        if level == 1:
            roots.append(node)
        else:
            parents[level - 2]["children"].append(node)

        parents = parents[: level - 1]
        parents.append(node)

    return roots


def _embedded_outline_entries(pdf: fitz.Document) -> list[list[Any]]:
    entries: list[list[Any]] = []
    for raw in pdf.get_toc(simple=False) or []:
        if len(raw) < 3:
            continue
        try:
            page = int(raw[2])
        except (TypeError, ValueError):
            continue
        if len(raw) > 3 and isinstance(raw[3], dict):
            dest_page = raw[3].get("page")
            if isinstance(dest_page, int) and dest_page >= 0:
                page = dest_page + 1
        entries.append([raw[0], raw[1], page])
    return entries


def _outline_is_usable(items: list[dict[str, Any]]) -> bool:
    flattened = _flatten_toc(items)
    if len(flattened) < 2:
        return False
    pages = {item["page"] for item in flattened if item.get("page")}
    if len(pages) < 2:
        return False
    generic = sum(
        1
        for item in flattened
        if _GENERIC_TITLE_RE.match(str(item.get("title") or "").strip())
        or str(item.get("title") or "").strip().lower() in {"untitled", "untitled section"}
    )
    return generic / len(flattened) <= 0.5


def _clean_toc_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title).strip(" \t.-")
    return title[:MAX_TOC_TITLE_LENGTH]


def _looks_like_toc_heading(value: str) -> bool:
    compact = re.sub(r"\s+", " ", value).strip(" :.-")
    if _TOC_HEADING_RE.match(compact):
        return True
    letters = re.sub(r"[^a-z]", "", compact.lower())
    if not 5 <= len(letters) <= 20:
        return False
    return max(
        SequenceMatcher(None, letters, candidate).ratio()
        for candidate in ("contents", "tableofcontents")
    ) >= 0.72


def _parse_printed_page_number(value: str) -> int:
    if value.isdigit():
        return int(value)
    total = 0
    previous = 0
    values = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}
    for character in reversed(value.lower()):
        current = values[character]
        total += -current if current < previous else current
        previous = max(previous, current)
    return total


def _parse_toc_line(text: str, *, allow_loose: bool = False) -> tuple[str, int] | None:
    stripped = text.strip()
    if not stripped or _looks_like_toc_heading(stripped) or _STOP_HEADING_RE.match(stripped):
        return None
    match = (
        _LEADER_PAGE_RE.match(stripped)
        or _NUMBERED_PAGE_RE.match(stripped)
        or _CHAPTER_PAGE_RE.match(stripped)
        or (_LOOSE_PAGE_RE.match(stripped) if allow_loose else None)
    )
    if not match:
        return None
    title = _clean_toc_title(match.group("title"))
    page = _parse_printed_page_number(match.group("page"))
    if not title or len(title) < 2 or _GENERIC_TITLE_RE.match(title):
        return None
    if 1900 <= page <= 2100 and not _NUMBER_PREFIX_RE.match(title) and not _CHAPTER_PREFIX_RE.match(title):
        return None
    return title, page


def _entry_level(title: str, x0: float, min_x: float) -> int:
    numbered = _NUMBER_PREFIX_RE.match(title)
    if numbered:
        number = numbered.group("number").strip(".")
        if re.match(r"^\d", number):
            return min(number.count(".") + 1, MAX_TOC_DEPTH)
        return 1
    if _CHAPTER_PREFIX_RE.match(title):
        return 1
    indent = max(0.0, x0 - min_x)
    if indent < 18:
        return 1
    if indent < 42:
        return 2
    return 3


def _looks_like_entry_start(value: str) -> bool:
    compact = _clean_toc_title(value).strip(" :.-")
    return bool(
        _NUMBER_PREFIX_RE.match(compact)
        or _CHAPTER_PREFIX_RE.match(compact)
        or _STRUCTURAL_HEADING_RE.match(compact)
    )


def _rows_from_words(words: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for word in sorted(words, key=lambda item: (round(float(item[1]) / 3) * 3, float(item[0]))):
        y = round(float(word[1]) / 3) * 3
        token = word[4] if isinstance(word[4], str) else str(word[4])
        x0, x1 = float(word[0]), float(word[2])
        if not rows or abs(rows[-1]["y"] - y) > 5:
            rows.append({"y": y, "x0": x0, "parts": [(x0, x1, token)]})
            continue
        rows[-1]["x0"] = min(rows[-1]["x0"], x0)
        rows[-1]["parts"].append((x0, x1, token))

    joined: list[dict[str, Any]] = []
    for row in rows:
        chunks: list[str] = []
        last_x1: float | None = None
        for x0, x1, token in row["parts"]:
            if last_x1 is not None and x0 - last_x1 > 28:
                chunks.append("  ")
            elif chunks:
                chunks.append(" ")
            chunks.append(token)
            last_x1 = x1
        text = "".join(chunks).strip()
        if text:
            joined.append({"x0": row["x0"], "text": text})
    return joined


def _page_row_variants(page: fitz.Page) -> list[list[dict[str, Any]]]:
    """Return single- and two-column readings of a page.

    Reading all words by y-position is best for conventional contents pages,
    while reading each half independently prevents same-height rows in a
    two-column contents page from being merged together.
    """
    words = list(page.get_text("words") or [])
    variants = [_rows_from_words(words)]
    midpoint = page.rect.width / 2
    gutter = max(12.0, page.rect.width * 0.025)
    left = [word for word in words if float(word[2]) <= midpoint + gutter]
    right = [word for word in words if float(word[0]) >= midpoint - gutter]
    if len(left) >= 6 and len(right) >= 6:
        left_rows = _rows_from_words(left)
        right_rows = _rows_from_words(right)
        left_origin = min((float(row["x0"]) for row in left_rows), default=0.0)
        right_origin = min((float(row["x0"]) for row in right_rows), default=midpoint)
        for row in left_rows:
            row["x0"] = float(row["x0"]) - left_origin
        for row in right_rows:
            # Compare indentation within a column, not against the left edge of
            # the page. Otherwise every right-column chapter looks deeply nested.
            row["x0"] = float(row["x0"]) - right_origin
        variants.append(left_rows + right_rows)
    return variants


def _ocr_page_rows(page: fitz.Page) -> list[dict[str, Any]]:
    """OCR one likely image-only page using the bundled local models."""
    from api.paddle_ocr_engine import PaddleOCREngineError, run_paddle_ocr_on_image

    pixmap = page.get_pixmap(matrix=fitz.Matrix(1.6, 1.6), alpha=False)
    try:
        detections = run_paddle_ocr_on_image(pixmap.tobytes("png"))
    except PaddleOCREngineError as exc:
        raise RuntimeError(str(exc)) from exc
    rows: list[dict[str, Any]] = []
    for detection in detections:
        if len(detection) < 2:
            continue
        points, raw_text = detection[0], detection[1]
        if not points or not raw_text:
            continue
        xs = [float(point[0]) for point in points]
        ys = [float(point[1]) for point in points]
        rows.append(
            {
                "x0": min(xs) / 1.6,
                "y0": min(ys) / 1.6,
                "text": str(raw_text).strip(),
            }
        )
    return sorted(rows, key=lambda row: (row["x0"] >= page.rect.width / 2, row["y0"], row["x0"]))


def _page_lines(page: fitz.Page) -> list[PageLine]:
    lines: list[PageLine] = []
    text = page.get_text("dict") or {}
    if not isinstance(text, dict):
        return lines
    for block in text.get("blocks", []):
        if block.get("type") != 0:
            continue
        for raw_line in block.get("lines", []):
            spans = [span for span in raw_line.get("spans", []) if str(span.get("text") or "").strip()]
            if not spans:
                continue
            value = _clean_toc_title(" ".join(str(span["text"]) for span in spans))
            bbox = raw_line.get("bbox") or spans[0].get("bbox")
            if not value or not bbox:
                continue
            lines.append(
                PageLine(
                    text=value,
                    x0=float(bbox[0]),
                    y0=float(bbox[1]),
                    x1=float(bbox[2]),
                    y1=float(bbox[3]),
                    size=max(float(span.get("size") or 0) for span in spans),
                    bold=any(
                        "bold" in str(span.get("font") or "").lower()
                        or bool(int(span.get("flags") or 0) & 16)
                        for span in spans
                    ),
                )
            )
    return lines


def _page_looks_like_bibliography(entries: list[tuple[str, int, int]]) -> bool:
    if len(entries) < 4:
        return False
    years = sum(1 for _title, page, _level in entries if 1900 <= page <= 2100)
    return years / len(entries) > 0.5


def _parse_printed_rows(
    rows: list[dict[str, Any]], page_count: int
) -> tuple[bool, bool, list[tuple[str, int, int]]]:
    has_heading = any(
        _looks_like_toc_heading(
            re.sub(r"\s+", " ", str(row.get("text") or "")).strip(" :.-")
        )
        for row in rows
    )
    heading_seen = False
    stop_after = False
    parsed_rows: list[tuple[str, int, float]] = []
    pending: tuple[str, float, int] | None = None

    for row in rows:
        text = str(row.get("text") or "").strip()
        compact = re.sub(r"\s+", " ", text).strip(" :.-")
        x0 = float(row.get("x0") or 0)
        if _looks_like_toc_heading(compact):
            heading_seen = True
            pending = None
            continue
        if _STOP_HEADING_RE.match(compact):
            stop_after = True
            break

        parsed = None
        if pending is not None:
            direct = _parse_toc_line(text, allow_loose=has_heading)
            direct_starts_entry = bool(
                direct and _looks_like_entry_start(direct[0])
            )
            continuation_geometry = x0 > pending[1] + 8
            if (
                _PAGE_ONLY_RE.match(compact)
                or continuation_geometry
                or not direct_starts_entry
            ):
                separator = "  " if _PAGE_ONLY_RE.match(compact) else " "
                joined = _parse_toc_line(
                    f"{pending[0]}{separator}{text}",
                    allow_loose=has_heading,
                )
                if joined is not None:
                    title, printed_page = joined
                    parsed_rows.append((title, printed_page, pending[1]))
                    pending = None
                    continue
        parsed = _parse_toc_line(text, allow_loose=has_heading)
        if parsed is not None:
            title, printed_page = parsed
            parsed_rows.append((title, printed_page, x0))
            pending = None
            continue

        if has_heading and heading_seen and _looks_like_entry_start(compact):
            parsed_rows.append((compact, 0, x0))
            pending = None
            continue
        if (
            has_heading
            and heading_seen
            and parsed_rows
            and parsed_rows[-1][1] == 0
            and 2 <= len(compact) <= 180
            and not compact.endswith((".", "!", "?"))
        ):
            previous_title, _page, previous_x0 = parsed_rows[-1]
            parsed_rows[-1] = (
                _clean_toc_title(f"{previous_title} {compact}"),
                0,
                previous_x0,
            )
            continue

        if (
            2 <= len(compact) <= MAX_TOC_TITLE_LENGTH
            and not compact.isdigit()
            and not compact.endswith((".", "!", "?", ":"))
        ):
            # Keep up to three wrapped rows, but start over when a clear new
            # chapter begins at the same indentation. This prevents an entry
            # without a page number from swallowing the next complete entry.
            if (
                pending is not None
                and pending[2] < 3
                and (
                    not _looks_like_entry_start(compact)
                    or x0 > pending[1] + 8
                )
            ):
                pending = (f"{pending[0]} {compact}", pending[1], pending[2] + 1)
            else:
                pending = (compact, x0, 1)
        else:
            pending = None

    if not parsed_rows:
        return has_heading, stop_after, []
    min_x = min(row[2] for row in parsed_rows)
    entries = [
        (title, printed_page, _entry_level(title, x0, min_x))
        for title, printed_page, x0 in parsed_rows
        if 0 <= printed_page <= max(page_count * 2, page_count)
    ]
    if _page_looks_like_bibliography(entries):
        return False, False, []
    return has_heading, stop_after, entries


def _extract_printed_entries_from_page(
    page: fitz.Page,
    page_count: int,
    *,
    ocr_rows: list[dict[str, Any]] | None = None,
) -> tuple[bool, bool, list[tuple[str, int, int]]]:
    variants = [ocr_rows] if ocr_rows is not None else _page_row_variants(page)
    candidates = [_parse_printed_rows(rows or [], page_count) for rows in variants]
    has_heading, stop_after, entries = max(
        candidates,
        key=lambda result: (bool(result[0]), len(result[2])),
    )
    is_toc_page = has_heading or len(entries) >= MIN_PRINTED_TOC_ENTRIES
    return is_toc_page, stop_after, entries


def _normalize_for_match(value: str) -> str:
    value = value.lower()
    value = _CHAPTER_PREFIX_RE.sub("", value)
    value = _NUMBER_PREFIX_RE.sub("", value)
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _map_printed_pages(
    pdf: fitz.Document,
    entries: list[tuple[str, int, int]],
    toc_end_index: int,
) -> list[list[Any]]:
    page_count = pdf.page_count
    segment_ids: list[int] = []
    segment_id = 0
    previous_printed_page: int | None = None
    for _title, printed_page, _level in entries:
        if (
            previous_printed_page is not None
            and printed_page + 2 < previous_printed_page
        ):
            segment_id += 1
        segment_ids.append(segment_id)
        previous_printed_page = printed_page

    direct_pages: dict[int, int] = {}
    offsets_by_segment: dict[int, list[int]] = {}
    page_text_cache: dict[int, str] = {}

    def normalized_page_text(page_index: int) -> str:
        if page_index not in page_text_cache:
            raw_text = pdf[page_index].get_text("text") or ""
            page_text_cache[page_index] = _normalize_for_match(str(raw_text)[:1400])
        return page_text_cache[page_index]

    sample_count = min(len(entries), 24)
    if sample_count == len(entries):
        sample_indexes = list(range(len(entries)))
    else:
        sample_indexes = sorted(
            {
                round(position * (len(entries) - 1) / max(sample_count - 1, 1))
                for position in range(sample_count)
            }
        )

    for entry_index in sample_indexes:
        title, printed_page, _level = entries[entry_index]
        needle = _normalize_for_match(title)
        if len(needle) < 6:
            continue
        if printed_page == 0:
            search_start = toc_end_index
            search_end = page_count
        else:
            expected_index = printed_page + max(toc_end_index, 1) - 1
            search_start = max(toc_end_index, expected_index - 12)
            search_end = min(page_count, expected_index + 36)
        found = next(
            (
                page_index + 1
                for page_index in range(search_start, search_end)
                if needle in normalized_page_text(page_index)
            ),
            None,
        )
        if found is None and entry_index in sample_indexes[:3]:
            # Front matter can create a large offset between printed and PDF
            # page numbers. Keep this fallback bounded instead of rescanning
            # every page for every entry.
            fallback_end = min(page_count, toc_end_index + 160)
            found = next(
                (
                    page_index + 1
                    for page_index in range(toc_end_index, fallback_end)
                    if needle in normalized_page_text(page_index)
                ),
                None,
            )
        if found is None:
            continue
        direct_pages[entry_index] = found
        if printed_page:
            offsets_by_segment.setdefault(segment_ids[entry_index], []).append(
                found - printed_page
            )

    segment_offsets: dict[int, int] = {}
    for current_segment, offsets in offsets_by_segment.items():
        offset = int(statistics.median(offsets))
        if len(offsets) == 1 or sum(abs(value - offset) <= 2 for value in offsets) >= 2:
            segment_offsets[current_segment] = offset
    all_offsets = [value for values in offsets_by_segment.values() for value in values]
    fallback_offset = int(statistics.median(all_offsets)) if all_offsets else None

    mapped: list[list[Any]] = []
    for entry_index, (title, printed_page, level) in enumerate(entries):
        offset = segment_offsets.get(segment_ids[entry_index], fallback_offset)
        page = direct_pages.get(
            entry_index,
            printed_page + offset if offset is not None else printed_page,
        )
        if printed_page == 0 and entry_index not in direct_pages:
            continue
        if page < 1 or page > page_count:
            if 1 <= printed_page <= page_count:
                page = printed_page
            else:
                continue
        mapped.append([level, title, page])
    return mapped


def _document_is_probably_image_only(pdf: fitz.Document) -> bool:
    sample_count = min(pdf.page_count, 6)
    if not sample_count:
        return False
    text_characters = 0
    image_pages = 0
    for index in range(sample_count):
        raw_text = pdf[index].get_text("text") or ""
        text_characters += len(re.sub(r"\s+", "", str(raw_text)))
        if pdf[index].get_images(full=True):
            image_pages += 1
    return text_characters < 200 and image_pages >= max(1, sample_count // 2)


def _scan_printed_table_of_contents(
    pdf: fitz.Document,
    progress_callback: ProgressCallback | None = None,
) -> list[list[Any]]:
    page_count = pdf.page_count
    scan_limit = min(page_count, MAX_PRINTED_TOC_SCAN_PAGES)
    collected: list[tuple[str, int, int]] = []
    started = False
    misses = 0
    toc_end_index = 0
    use_ocr = _document_is_probably_image_only(pdf)
    ocr_used = False
    ocr_started_at = time.monotonic()

    try:
        for index in range(scan_limit):
            ocr_rows = None
            message = f"Scanning page {index + 1} of {scan_limit} for a printed contents list…"
            if use_ocr and index < MAX_OCR_TOC_SCAN_PAGES:
                message = (
                    f"Reading scanned page {index + 1} of "
                    f"{min(scan_limit, MAX_OCR_TOC_SCAN_PAGES)} with OCR…"
                )
            _report_progress(
                progress_callback,
                30 + int(50 * (index + 1) / max(scan_limit, 1)),
                message,
            )
            if use_ocr and index < MAX_OCR_TOC_SCAN_PAGES:
                try:
                    ocr_rows = _ocr_page_rows(pdf[index])
                    ocr_used = True
                except (ImportError, OSError, RuntimeError) as exc:
                    print(f"TOC OCR fallback unavailable: {exc}")
                    use_ocr = False

            is_toc_page, stop_after, entries = _extract_printed_entries_from_page(
                pdf[index],
                page_count,
                ocr_rows=ocr_rows,
            )
            if is_toc_page and entries:
                started = True
                misses = 0
                collected.extend(entries)
                toc_end_index = index + 1
                if len(collected) >= MAX_TOC_ITEMS:
                    collected = collected[:MAX_TOC_ITEMS]
                    break
                if stop_after:
                    break
                continue
            if started:
                misses += 1
                if misses >= 2 or stop_after:
                    break
            if use_ocr and index + 1 >= MAX_OCR_TOC_SCAN_PAGES and not started:
                break
            if (
                use_ocr
                and not started
                and time.monotonic() - ocr_started_at >= MAX_OCR_TOC_SECONDS
            ):
                break
    finally:
        if ocr_used:
            from api.paddle_ocr_engine import release_paddle_ocr_engine

            release_paddle_ocr_engine()

    if len(collected) < MIN_PRINTED_TOC_ENTRIES:
        return []
    _report_progress(progress_callback, 86, "Matching contents titles to PDF pages…")
    return _map_printed_pages(pdf, collected, toc_end_index)


def _body_font_size(pages: list[list[PageLine]]) -> float:
    weighted_sizes: Counter[float] = Counter()
    for lines in pages:
        for line in lines:
            if len(line.text) < 20:
                continue
            weighted_sizes[round(line.size * 2) / 2] += min(len(line.text), 300)
    if not weighted_sizes:
        return 10.0
    return weighted_sizes.most_common(1)[0][0]


def _infer_heading_level(
    title: str,
    size: float,
    font_size_levels: list[float],
) -> int:
    numbered = _SECTION_NUMBER_RE.match(title)
    if numbered:
        return min(numbered.group("number").count(".") + 1, MAX_TOC_DEPTH)
    if _STRUCTURAL_HEADING_RE.match(title.strip(" :.-")) or _CHAPTER_PREFIX_RE.match(title):
        return 1
    if not font_size_levels:
        return 1
    nearest = min(
        range(len(font_size_levels)),
        key=lambda index: abs(font_size_levels[index] - size),
    )
    return min(nearest + 1, 3)


def _infer_document_outline(
    pdf: fitz.Document,
    progress_callback: ProgressCallback | None = None,
) -> list[list[Any]]:
    """Build an outline from visible section headings when no TOC exists."""
    pages: list[list[PageLine]] = []
    page_count = pdf.page_count
    for index in range(page_count):
        if index == 0 or index == page_count - 1 or index % max(1, page_count // 12) == 0:
            _report_progress(
                progress_callback,
                87 + int(8 * (index + 1) / max(page_count, 1)),
                f"Finding section headings on page {index + 1} of {page_count}…",
            )
        if index < MAX_PRINTED_TOC_SCAN_PAGES:
            is_contents_page, _stop_after, contents_entries = (
                _extract_printed_entries_from_page(pdf[index], page_count)
            )
            if is_contents_page and contents_entries:
                pages.append([])
                continue
        pages.append(_page_lines(pdf[index]))

    body_size = _body_font_size(pages)
    occurrences: Counter[str] = Counter()
    for lines in pages:
        occurrences.update({_normalize_for_match(line.text) for line in lines if line.text})
    repeated_limit = max(3, int(page_count * 0.15))

    raw_candidates: list[tuple[str, int, float]] = []
    found_structure = False
    for page_index, lines in enumerate(pages):
        page_height = pdf[page_index].rect.height
        for line in lines:
            title = _clean_toc_title(line.text)
            normalized = _normalize_for_match(title)
            if (
                not normalized
                or len(title) < 3
                or len(title) > 180
                or line.y0 > page_height * 0.92
                or occurrences[normalized] >= repeated_limit
                or _REJECTED_HEADING_RE.match(title)
            ):
                continue

            numbered = _SECTION_NUMBER_RE.match(title)
            structural = bool(
                _STRUCTURAL_HEADING_RE.match(title.strip(" :.-"))
                or _CHAPTER_PREFIX_RE.match(title)
            )
            typographic = line.size >= body_size + 1.0 or (
                line.bold and line.size >= body_size + 0.25
            )
            if not (numbered or structural or typographic):
                continue
            if not (numbered or structural):
                if len(title.split()) > 16 or title[-1:] in {".", ",", ";"}:
                    continue
                if title[:1].islower():
                    continue

            # Ignore article titles and author names before the first recognizable
            # section. Large-font candidates are accepted after structure starts.
            if numbered or structural:
                found_structure = True
            elif not found_structure:
                continue
            raw_candidates.append((title, page_index + 1, line.size))

    if len(raw_candidates) < MIN_INFERRED_TOC_ENTRIES:
        return []

    font_size_levels = sorted(
        {round(size * 2) / 2 for _title, _page, size in raw_candidates},
        reverse=True,
    )[:3]
    entries: list[list[Any]] = []
    seen: set[tuple[str, int]] = set()
    for title, page, size in raw_candidates:
        identity = (_normalize_for_match(title), page)
        if identity in seen:
            continue
        seen.add(identity)
        entries.append([_infer_heading_level(title, size, font_size_levels), title, page])
        if len(entries) >= MAX_TOC_ITEMS:
            break

    if (
        len(entries) < MIN_INFERRED_TOC_ENTRIES
        or len({int(entry[2]) for entry in entries}) < 2
    ):
        return []
    return entries


def _infer_large_document_outline_fast(
    pdf: fitz.Document,
    progress_callback: ProgressCallback | None = None,
) -> list[list[Any]]:
    """Use only structural text patterns on large documents.

    This deliberately avoids expensive span/font analysis on every page.
    """
    entries: list[list[Any]] = []
    seen: set[str] = set()
    page_count = pdf.page_count
    for page_index in range(page_count):
        if page_index == 0 or page_index == page_count - 1 or page_index % 50 == 0:
            _report_progress(
                progress_callback,
                87 + int(8 * (page_index + 1) / max(page_count, 1)),
                f"Checking chapter headings on page {page_index + 1} of {page_count}…",
            )
        raw_text = pdf[page_index].get_text("text") or ""
        lines = [
            _clean_toc_title(line)
            for line in str(raw_text).splitlines()[:16]
            if line.strip()
        ]
        for title in lines:
            compact = title.strip(" :.-")
            numbered = _SECTION_NUMBER_RE.match(title)
            structural = bool(
                _STRUCTURAL_HEADING_RE.match(compact)
                or _CHAPTER_PREFIX_RE.match(title)
            )
            if (
                not (numbered or structural)
                or len(title) > 140
                or _REJECTED_HEADING_RE.match(title)
            ):
                continue
            if numbered:
                numbered_title = numbered.group("title")
                if numbered_title[:1].islower() or len(numbered_title.split()) > 14:
                    continue
            normalized = _normalize_for_match(title)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            entries.append(
                [
                    _infer_heading_level(title, 0, []),
                    title,
                    page_index + 1,
                ]
            )
            if len(entries) >= MAX_FAST_INFERRED_TOC_ITEMS:
                break
        if len(entries) >= MAX_FAST_INFERRED_TOC_ITEMS:
            break

    if (
        len(entries) < MIN_INFERRED_TOC_ENTRIES
        or len({int(entry[2]) for entry in entries}) < 2
    ):
        return []
    return entries


def _title_similarity(left: str, right: str) -> float:
    left_normalized = _normalize_for_match(left)
    right_normalized = _normalize_for_match(right)
    if not left_normalized or not right_normalized:
        return 0.0
    if left_normalized == right_normalized:
        return 1.0
    left_tokens = set(left_normalized.split())
    right_tokens = set(right_normalized.split())
    overlap = len(left_tokens & right_tokens) / max(len(left_tokens | right_tokens), 1)
    sequence = SequenceMatcher(None, left_normalized, right_normalized).ratio()
    containment = (
        min(len(left_normalized), len(right_normalized))
        / max(len(left_normalized), len(right_normalized))
        if left_normalized in right_normalized or right_normalized in left_normalized
        else 0.0
    )
    return max(overlap, sequence, containment)


def _printed_entries_need_reconciliation(
    entries: list[list[Any]],
    page_count: int,
) -> bool:
    small_document_toc = (
        len(entries) <= MAX_RECONCILIATION_TOC_ENTRIES
        and page_count <= 200
    )
    previous_page: int | None = None
    for _level, raw_title, raw_page, *_rest in entries:
        title = str(raw_title)
        page = int(raw_page)
        if len(_ENTRY_MARKER_RE.findall(title)) >= 2:
            return True
        if previous_page is not None and page + 2 < previous_page:
            return True
        previous_page = page
    return small_document_toc


def _reconcile_printed_with_inferred(
    printed: list[list[Any]],
    inferred: list[list[Any]],
) -> tuple[list[list[Any]], bool]:
    """Split merged entries and restore entries omitted from a printed TOC."""
    if not printed or not inferred:
        return printed, False

    reconciled: list[list[Any]] = []
    used_inferred: set[int] = set()
    changed = False

    for printed_entry in printed:
        printed_level, printed_title, printed_page = printed_entry[:3]
        printed_normalized = _normalize_for_match(str(printed_title))
        contained: list[tuple[int, list[Any]]] = []
        for index, inferred_entry in enumerate(inferred):
            inferred_normalized = _normalize_for_match(str(inferred_entry[1]))
            if (
                len(inferred_normalized) >= 4
                and inferred_normalized in printed_normalized
            ):
                contained.append((index, inferred_entry))

        # A line such as "Chapter 2 Methods Chapter 3 Results 18" is one
        # extraction row but represents multiple real headings.
        distinct_pages = {int(entry[2]) for _index, entry in contained}
        if len(contained) >= 2 and len(distinct_pages) >= 2:
            for index, inferred_entry in contained:
                reconciled.append(list(inferred_entry[:3]))
                used_inferred.add(index)
            changed = True
            continue

        best_index = -1
        best_score = 0.0
        for index, inferred_entry in enumerate(inferred):
            if index in used_inferred:
                continue
            score = _title_similarity(str(printed_title), str(inferred_entry[1]))
            page_distance = abs(int(printed_page) - int(inferred_entry[2]))
            if page_distance > 8:
                score -= min(0.25, (page_distance - 8) * 0.02)
            if score > best_score:
                best_index = index
                best_score = score

        if best_index >= 0 and best_score >= 0.68:
            inferred_entry = inferred[best_index]
            reconciled.append(
                [printed_level, printed_title, int(inferred_entry[2])]
            )
            used_inferred.add(best_index)
            changed = changed or int(printed_page) != int(inferred_entry[2])
        else:
            reconciled.append(list(printed_entry[:3]))

    for index, inferred_entry in enumerate(inferred):
        if index not in used_inferred:
            reconciled.append(list(inferred_entry[:3]))
            changed = True

    reconciled.sort(key=lambda entry: (int(entry[2]), int(entry[0])))
    deduplicated: list[list[Any]] = []
    seen: set[tuple[str, int]] = set()
    for entry in reconciled:
        identity = (_normalize_for_match(str(entry[1])), int(entry[2]))
        if identity in seen:
            changed = True
            continue
        seen.add(identity)
        deduplicated.append(entry)
    return deduplicated, changed


def extract_document_table_of_contents(
    file_path: str | Path,
    progress_callback: ProgressCallback | None = None,
) -> tuple[list[dict[str, Any]], int, str]:
    with fitz.open(str(file_path)) as pdf:
        page_count = pdf.page_count
        _report_progress(progress_callback, 12, "Opening PDF…")
        embedded = _build_toc_tree(_embedded_outline_entries(pdf), page_count)
        _report_progress(progress_callback, 28, "Read the PDF's embedded chapter outline.")
        printed_entries = _scan_printed_table_of_contents(pdf, progress_callback)

        embedded_count = len(_flatten_toc(embedded))
        embedded_usable = _outline_is_usable(embedded)
        inferred_entries: list[list[Any]] = []
        if (
            printed_entries
            and page_count <= MAX_DETAILED_INFERENCE_PAGES
            and _printed_entries_need_reconciliation(printed_entries, page_count)
        ):
            inferred_entries = _infer_document_outline(pdf, progress_callback)
        elif not printed_entries and not embedded_usable:
            if page_count <= MAX_DETAILED_INFERENCE_PAGES:
                inferred_entries = _infer_document_outline(pdf, progress_callback)
            else:
                inferred_entries = _infer_large_document_outline_fast(
                    pdf,
                    progress_callback,
                )

        printed_augmented = False
        if printed_entries and inferred_entries:
            printed_entries, printed_augmented = _reconcile_printed_with_inferred(
                printed_entries,
                inferred_entries,
            )
        printed = _build_toc_tree(printed_entries, page_count)
        inferred = _build_toc_tree(inferred_entries, page_count)
        printed_count = len(_flatten_toc(printed))

        if printed_count and (not embedded_usable or printed_count >= max(4, int(embedded_count * 1.5))):
            source = "hybrid" if printed_augmented else "printed"
            items = printed
        elif embedded_usable:
            source = "embedded"
            items = embedded
        elif inferred:
            source = "inferred"
            items = inferred
        elif embedded:
            source = "embedded"
            items = embedded
        else:
            source = ""
            items = []

        _report_progress(progress_callback, 96, "Building the chapter list…")
        return items, page_count, source


def sanitize_table_of_contents(
    items: Any,
    *,
    page_count: int = 0,
    depth: int = 0,
    counter: list[int] | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        raise ValueError("Table of contents must be a list.")
    if not items:
        return []
    if depth >= MAX_TOC_DEPTH:
        raise ValueError(f"Table of contents cannot exceed {MAX_TOC_DEPTH} levels.")

    counter = counter if counter is not None else [0]
    sanitized = []
    for item in items:
        counter[0] += 1
        if counter[0] > MAX_TOC_ITEMS:
            raise ValueError(f"Table of contents cannot exceed {MAX_TOC_ITEMS} entries.")
        if not isinstance(item, dict):
            raise ValueError("Every table of contents entry must be an object.")

        title = str(item.get("title") or "").strip()
        if not title:
            raise ValueError("Every table of contents entry needs a title.")
        if len(title) > MAX_TOC_TITLE_LENGTH:
            raise ValueError(
                f"Table of contents titles cannot exceed {MAX_TOC_TITLE_LENGTH} characters."
            )

        raw_page = item.get("page")
        try:
            if raw_page is None or isinstance(raw_page, bool):
                raise TypeError("missing page")
            page = int(raw_page)
        except (TypeError, ValueError) as exc:
            raise ValueError(f'"{title}" needs a valid PDF page number.') from exc
        if page < 1 or (page_count and page > page_count):
            maximum = f" and {page_count}" if page_count else ""
            raise ValueError(f'"{title}" page must be between 1{maximum}.')

        item_id = str(item.get("id") or uuid.uuid4())[:100]
        sanitized.append(
            {
                "id": item_id,
                "title": title,
                "page": page,
                "children": sanitize_table_of_contents(
                    item.get("children", []),
                    page_count=page_count,
                    depth=depth + 1,
                    counter=counter,
                ),
            }
        )
    return sanitized


def _remove_queued_toc_tasks(document_id: int, task_id: str = "") -> None:
    from django_q.models import OrmQ

    for queued in OrmQ.objects.all():
        task = queued.task
        if task.get("func") != TOC_TASK_FUNCTION:
            continue
        if task_id and task.get("id") == task_id:
            queued.delete()
            continue
        args = task.get("args") or []
        if args and str(args[0]) == str(document_id):
            queued.delete()


def cancel_document_table_of_contents(document: Document, reason: str) -> Document:
    """Cancel a TOC job without discarding the user's saved outline."""
    _remove_queued_toc_tasks(document.pk, document.toc_task_id)
    document.toc_status = Document.TocStatus.CANCELLED
    document.toc_error = reason
    document.toc_completed_at = timezone.now()
    document.toc_task_id = ""
    document.toc_progress_message = reason[:200]
    document.save(
        update_fields=[
            "toc_status",
            "toc_error",
            "toc_completed_at",
            "toc_task_id",
            "toc_progress_message",
        ]
    )
    return document


def cancel_incomplete_table_of_contents(reason: str = "Cancelled because Research Marker closed.") -> int:
    documents = list(Document.objects.filter(toc_status__in=[Document.TocStatus.QUEUED, Document.TocStatus.PROCESSING]))
    for document in documents:
        cancel_document_table_of_contents(document, reason)
    return len(documents)


def _save_document_progress(document: Document, percent: int, message: str) -> bool:
    document.refresh_from_db(fields=["toc_status"])
    if document.toc_status == Document.TocStatus.CANCELLED:
        return False
    document.toc_progress = max(0, min(100, percent))
    document.toc_progress_message = message[:200]
    document.save(update_fields=["toc_progress", "toc_progress_message"])
    return True


def scrape_document_table_of_contents(document_id: int) -> None:
    try:
        document = Document.objects.get(pk=document_id)
    except Document.DoesNotExist:
        print(f"TOC scrape skipped: document {document_id} no longer exists.")
        return

    if document.toc_status == Document.TocStatus.CANCELLED:
        return

    document.toc_status = Document.TocStatus.PROCESSING
    document.toc_error = ""
    document.toc_started_at = timezone.now()
    document.toc_completed_at = None
    document.toc_progress = 5
    document.toc_progress_message = "Starting table of contents scrape…"
    document.save(
        update_fields=[
            "toc_status",
            "toc_error",
            "toc_started_at",
            "toc_completed_at",
            "toc_progress",
            "toc_progress_message",
        ]
    )

    try:
        if not document.file:
            raise ValueError("Document has no PDF file.")

        def on_progress(percent: int, message: str) -> bool:
            return _save_document_progress(document, percent, message)

        toc_data, page_count, source = extract_document_table_of_contents(
            document.file.path,
            progress_callback=on_progress,
        )
        document.refresh_from_db(fields=["toc_status"])
        if document.toc_status == Document.TocStatus.CANCELLED:
            return
        document.toc_data = toc_data
        document.toc_source = source
        document.toc_status = Document.TocStatus.SUCCEEDED
        document.toc_error = ""
        document.toc_completed_at = timezone.now()
        document.toc_task_id = ""
        document.toc_progress = 100
        document.toc_progress_message = (
            f"Found {len(_flatten_toc(toc_data))} chapters."
            if toc_data
            else "No table of contents entries were found."
        )
        if not document.page_count:
            document.page_count = page_count
        document.save(
            update_fields=[
                "toc_data",
                "toc_source",
                "toc_status",
                "toc_error",
                "toc_completed_at",
                "page_count",
                "toc_task_id",
                "toc_progress",
                "toc_progress_message",
            ]
        )
    except TocCancelled:
        return
    except Exception as exc:
        document.refresh_from_db(fields=["toc_status"])
        if document.toc_status == Document.TocStatus.CANCELLED:
            return
        document.toc_status = Document.TocStatus.FAILED
        document.toc_error = str(exc)[:2000]
        document.toc_completed_at = timezone.now()
        document.toc_task_id = ""
        document.toc_progress_message = "Table of contents scrape failed."
        document.save(
            update_fields=[
                "toc_status",
                "toc_error",
                "toc_completed_at",
                "toc_task_id",
                "toc_progress_message",
            ]
        )
        print(f"TOC scrape failed for document {document_id}: {exc}")
