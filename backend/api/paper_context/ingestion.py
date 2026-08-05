from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
import hashlib
import json
import logging
import math
from pathlib import Path
import re
import shutil
from typing import Any

import fitz
from PIL import Image
from django.db import connection, transaction
from django.utils import timezone

from api import models
from api.errors import DocumentNotFound, OCRFailed, PageExtractionFailed
from api.paddle_ocr_engine import PaddleOCREngineError, run_paddle_ocr_on_image
from api.utils import get_app_data_dir

LOGGER = logging.getLogger(__name__)
RENDER_DPI = 168
RENDERER_VERSION = f"pymupdf-{fitz.VersionBind}-dpi{RENDER_DPI}-png"
OCR_CONFIGURATION = "rapidocr-ppocrv4-default-v1"
SPARSE_TEXT_CHARACTERS = 80
MAX_RENDER_DIMENSION = 3200
THUMBNAIL_DIMENSION = 360


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _cache_root(document_hash: str) -> Path:
    return Path(get_app_data_dir()) / "paper_context" / document_hash


def _safe_text(value: str) -> str:
    value = value.replace("\x00", " ").replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[ \t]+\n", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _embedded_blocks(page: fitz.Page) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for raw in page.get_text("blocks", sort=True):
        if len(raw) < 7 or raw[6] != 0:
            continue
        text = _safe_text(str(raw[4]))
        if not text:
            continue
        blocks.append(
            {
                "bbox": [round(float(value), 3) for value in raw[:4]],
                "text": text,
                "block_number": int(raw[5]),
                "source": "embedded",
            }
        )
    return blocks


def _text_is_corrupt(text: str) -> bool:
    if not text:
        return True
    replacement_ratio = text.count("\ufffd") / max(len(text), 1)
    control_ratio = sum(ord(char) < 9 or 13 < ord(char) < 32 for char in text) / max(
        len(text), 1
    )
    return replacement_ratio > 0.02 or control_ratio > 0.01


def _needs_ocr(text: str, page: fitz.Page) -> bool:
    compact = re.sub(r"\s+", "", text)
    if _text_is_corrupt(text) or len(compact) < SPARSE_TEXT_CHARACTERS:
        return True
    image_area = 0.0
    for image in page.get_image_info():
        bbox = image.get("bbox")
        if bbox:
            image_area += max(0.0, (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]))
    page_area = max(page.rect.width * page.rect.height, 1)
    return image_area / page_area > 0.85 and len(compact) < 350


def _render_page(page: fitz.Page, image_path: Path, thumbnail_path: Path) -> bytes:
    scale = RENDER_DPI / 72
    longest = max(page.rect.width, page.rect.height) * scale
    if longest > MAX_RENDER_DIMENSION:
        scale *= MAX_RENDER_DIMENSION / longest
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False, colorspace=fitz.csRGB)
    png_bytes = pix.tobytes("png")
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(png_bytes)
    with Image.open(image_path) as image:
        image.thumbnail((THUMBNAIL_DIMENSION, THUMBNAIL_DIMENSION))
        image.save(thumbnail_path, format="PNG", optimize=True)
    return png_bytes


def _ocr_cache_key(document_hash: str, page_number: int) -> str:
    raw = f"{document_hash}:{page_number}:{RENDERER_VERSION}:{OCR_CONFIGURATION}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _ocr_page(
    *,
    png_bytes: bytes,
    page: fitz.Page,
    cache_path: Path,
    cache_key: str,
) -> tuple[list[dict], float | None]:
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if cached.get("cache_key") == cache_key:
                return cached.get("blocks", []), cached.get("confidence")
        except (OSError, ValueError):
            pass

    try:
        rows = run_paddle_ocr_on_image(png_bytes)
    except PaddleOCREngineError as exc:
        raise OCRFailed(str(exc)) from exc

    with Image.open(cache_path.parent / f"{cache_path.stem.removesuffix('.ocr')}.png") as image:
        image_width, image_height = image.size
    scale_x = page.rect.width / max(image_width, 1)
    scale_y = page.rect.height / max(image_height, 1)
    blocks: list[dict] = []
    confidences: list[float] = []
    for index, row in enumerate(rows):
        if len(row) < 3:
            continue
        points, text, confidence = row
        clean_text = _safe_text(str(text))
        if not clean_text:
            continue
        xs = [float(point[0]) * scale_x for point in points]
        ys = [float(point[1]) * scale_y for point in points]
        score = float(confidence) if confidence is not None else None
        if score is not None:
            confidences.append(score)
        blocks.append(
            {
                "bbox": [round(min(xs), 3), round(min(ys), 3), round(max(xs), 3), round(max(ys), 3)],
                "text": clean_text,
                "block_number": index,
                "source": "ocr",
                "confidence": score,
            }
        )
    average = sum(confidences) / len(confidences) if confidences else None
    cache_path.write_text(
        json.dumps({"cache_key": cache_key, "blocks": blocks, "confidence": average}),
        encoding="utf-8",
    )
    return blocks, average


def _page_text(blocks: list[dict]) -> str:
    return "\n\n".join(block["text"] for block in blocks if block.get("text")).strip()


def _header_footer_candidates(page_data: list[dict]) -> set[str]:
    counts: Counter[str] = Counter()
    for item in page_data:
        height = max(item["height"], 1)
        seen: set[str] = set()
        for block in item["blocks"]:
            y0, y1 = block["bbox"][1], block["bbox"][3]
            if y0 <= height * 0.08 or y1 >= height * 0.92:
                for line in block["text"].splitlines():
                    normalized = re.sub(r"\s+", " ", line).strip()
                    if 4 <= len(normalized) <= 160:
                        seen.add(normalized)
        counts.update(seen)
    threshold = max(3, math.ceil(len(page_data) * 0.7))
    return {text for text, count in counts.items() if count >= threshold}


def _remove_repeated_margins(page_data: list[dict]) -> None:
    repeated = _header_footer_candidates(page_data)
    if not repeated:
        return
    for item in page_data:
        height = max(item["height"], 1)
        retained: list[dict] = []
        for block in item["blocks"]:
            y0, y1 = block["bbox"][1], block["bbox"][3]
            is_margin = y0 <= height * 0.08 or y1 >= height * 0.92
            lines = block["text"].splitlines()
            if is_margin:
                lines = [line for line in lines if re.sub(r"\s+", " ", line).strip() not in repeated]
            text = _safe_text("\n".join(lines))
            if text:
                retained.append({**block, "text": text})
        item["blocks"] = retained
        item["text"] = _page_text(retained)


def _complexity(page: fitz.Page, blocks: list[dict], text: str, confidence: float | None) -> list[str]:
    reasons: list[str] = []
    lowered = text.lower()
    if page.get_images(full=True):
        reasons.append("embedded_image")
    if re.search(r"\b(figure|fig\.|table|chart|diagram|caption)\b", lowered):
        reasons.append("visual_reference")
    if re.search(r"(?:^|\s)(?:[a-zA-Z]\s*=|∑|∫|√|≤|≥|≈|\\frac|equation\s+\(?\d)", text):
        reasons.append("equation")
    if re.search(r"\btable\s+\d+|\|\s*[-:]+\s*\|", lowered):
        reasons.append("table")
    left_edges = [block["bbox"][0] for block in blocks if len(block.get("text", "")) > 30]
    if len(left_edges) >= 2:
        clusters = {round(edge / max(page.rect.width, 1) * 10) for edge in left_edges}
        if len(clusters) >= 2 and max(left_edges) - min(left_edges) > page.rect.width * 0.25:
            reasons.append("multi_column")
    if len(re.sub(r"\s+", "", text)) < SPARSE_TEXT_CHARACTERS:
        reasons.append("sparse_text")
    if confidence is not None and confidence < 0.75:
        reasons.append("low_ocr_confidence")
    return list(dict.fromkeys(reasons))


def _section_title(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if 3 <= len(line) <= 120 and (line.isupper() or re.match(r"^\d+(?:\.\d+)*\s+\S+", line)):
            return line
    return ""


def _chunks_for_page(document: models.Document, page_number: int, text: str) -> list[models.DocumentChunk]:
    paragraphs = [value.strip() for value in re.split(r"\n\s*\n", text) if value.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if current and len(current) + len(paragraph) + 2 > 4_500:
            chunks.append(current)
            current = paragraph
        else:
            current = f"{current}\n\n{paragraph}".strip()
    if current:
        chunks.append(current)
    if not chunks and text:
        chunks = [text[:4_500]]

    results: list[models.DocumentChunk] = []
    for index, chunk_text in enumerate(chunks):
        chunk_id = f"{document.document_hash[:24]}-p{page_number}-c{index}"
        results.append(
            models.DocumentChunk(
                document=document,
                chunk_id=chunk_id,
                start_page=page_number,
                end_page=page_number,
                chunk_text=chunk_text,
                normalized_text=re.sub(r"\s+", " ", chunk_text).lower(),
                section_title=_section_title(chunk_text),
            )
        )
    return results


def _rebuild_fts(document_id: int) -> None:
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS api_documentchunk_fts
                USING fts5(chunk_id UNINDEXED, document_id UNINDEXED, chunk_text, section_title)
                """
            )
            cursor.execute("DELETE FROM api_documentchunk_fts WHERE document_id = %s", [document_id])
            rows = models.DocumentChunk.objects.filter(document_id=document_id).values_list(
                "chunk_id", "document_id", "chunk_text", "section_title"
            )
            cursor.executemany(
                """
                INSERT INTO api_documentchunk_fts
                (chunk_id, document_id, chunk_text, section_title)
                VALUES (%s, %s, %s, %s)
                """,
                list(rows),
            )
    except Exception as exc:
        LOGGER.warning("SQLite FTS5 unavailable; retrieval will use a local fallback: %s", exc)


def ingest_document(document_id: int, *, allow_ocr: bool = True, force: bool = False) -> str:
    try:
        document = models.Document.objects.get(pk=document_id)
    except models.Document.DoesNotExist as exc:
        raise DocumentNotFound(f"Document {document_id} was not found.") from exc
    if not document.file:
        raise DocumentNotFound(f"Document {document_id} has no PDF file.")

    pdf_path = Path(document.file.path).resolve()
    if not pdf_path.is_file():
        raise DocumentNotFound(f"The PDF for document {document_id} is missing.")
    document_hash = _sha256(pdf_path)
    if (
        not force
        and document.document_hash == document_hash
        and document.context_status == "ready"
        and document.context_pages.exists()
    ):
        return "cached"

    document.context_status = "processing"
    document.context_error = ""
    document.save(update_fields=["context_status", "context_error"])
    cache_root = _cache_root(document_hash)
    pages_dir = cache_root / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    page_data: list[dict] = []
    pdf: fitz.Document | None = None
    try:
        pdf = fitz.open(pdf_path)
        for page_index in range(pdf.page_count):
            page_number = page_index + 1
            page = pdf.load_page(page_index)
            image_path = pages_dir / f"page-{page_number}.png"
            thumbnail_path = pages_dir / f"page-{page_number}-thumb.png"
            extraction_error = ""
            embedded: list[dict] = []
            try:
                embedded = _embedded_blocks(page)
            except Exception as exc:
                extraction_error = str(exc)
            text = _page_text(embedded)
            png_bytes = _render_page(page, image_path, thumbnail_path)
            blocks = embedded
            ocr_used = False
            confidence = None
            source_type = models.DocumentPage.SourceType.EMBEDDED
            cache_key = _ocr_cache_key(document_hash, page_number)

            if allow_ocr and _needs_ocr(text, page):
                cache_path = pages_dir / f"page-{page_number}.ocr.json"
                try:
                    ocr_blocks, confidence = _ocr_page(
                        png_bytes=png_bytes,
                        page=page,
                        cache_path=cache_path,
                        cache_key=cache_key,
                    )
                    if ocr_blocks:
                        ocr_used = True
                        if embedded and len(text.strip()) >= SPARSE_TEXT_CHARACTERS:
                            blocks = embedded + ocr_blocks
                            source_type = models.DocumentPage.SourceType.COMBINED
                        else:
                            blocks = ocr_blocks
                            source_type = models.DocumentPage.SourceType.OCR
                        text = _page_text(blocks)
                except Exception as exc:
                    extraction_error = f"{extraction_error}; OCR: {exc}".strip("; ")

            if not text and extraction_error:
                source_type = models.DocumentPage.SourceType.FAILED
            reasons = _complexity(page, blocks, text, confidence)
            page_data.append(
                {
                    "page_number": page_number,
                    "blocks": blocks,
                    "text": text,
                    "page_image_path": str(image_path.resolve()),
                    "thumbnail_path": str(thumbnail_path.resolve()),
                    "source_type": source_type,
                    "ocr_used": ocr_used,
                    "ocr_confidence": confidence,
                    "width": float(page.rect.width),
                    "height": float(page.rect.height),
                    "rotation": int(page.rotation),
                    "visually_complex": bool(reasons),
                    "complexity_reasons": reasons,
                    "extraction_error": extraction_error,
                    "ocr_cache_key": cache_key if ocr_used else "",
                }
            )
        _remove_repeated_margins(page_data)

        now = timezone.now()
        with transaction.atomic():
            document.document_hash = document_hash
            document.file_name = pdf_path.name
            document.absolute_local_path = str(pdf_path)
            document.page_count = pdf.page_count
            document.context_status = "ready"
            document.context_error = ""
            document.context_created_at = document.context_created_at or now
            document.context_updated_at = now
            document.save(
                update_fields=[
                    "document_hash",
                    "file_name",
                    "absolute_local_path",
                    "page_count",
                    "context_status",
                    "context_error",
                    "context_created_at",
                    "context_updated_at",
                ]
            )
            document.context_pages.all().delete()
            document.context_chunks.all().delete()
            pages = [
                models.DocumentPage(
                    document=document,
                    page_number=item["page_number"],
                    extracted_text=item["text"],
                    text_blocks=item["blocks"],
                    page_image_path=item["page_image_path"],
                    thumbnail_path=item["thumbnail_path"],
                    source_type=item["source_type"],
                    ocr_used=item["ocr_used"],
                    ocr_confidence=item["ocr_confidence"],
                    width=item["width"],
                    height=item["height"],
                    rotation=item["rotation"],
                    visually_complex=item["visually_complex"],
                    complexity_reasons=item["complexity_reasons"],
                    extraction_error=item["extraction_error"],
                    ocr_cache_key=item["ocr_cache_key"],
                    renderer_version=RENDERER_VERSION,
                )
                for item in page_data
            ]
            models.DocumentPage.objects.bulk_create(pages)
            chunks: list[models.DocumentChunk] = []
            for item in page_data:
                chunks.extend(_chunks_for_page(document, item["page_number"], item["text"]))
            models.DocumentChunk.objects.bulk_create(chunks)
        _rebuild_fts(document.id)
        return "success"
    except (DocumentNotFound, OCRFailed):
        raise
    except Exception as exc:
        models.Document.objects.filter(pk=document_id).update(
            context_status="failed",
            context_error=str(exc)[:2000],
            context_updated_at=timezone.now(),
        )
        raise PageExtractionFailed(
            "The paper context could not be generated.",
            details={"document_id": document_id},
        ) from exc
    finally:
        if pdf is not None:
            pdf.close()


def ensure_document_ingested(document_id: int) -> models.Document:
    try:
        document = models.Document.objects.get(pk=document_id)
    except models.Document.DoesNotExist as exc:
        raise DocumentNotFound(f"Document {document_id} was not found.") from exc
    if not document.file:
        raise DocumentNotFound(f"Document {document_id} has no PDF file.")
    path = Path(document.file.path)
    if document.ocr_status in (
        models.Document.OcrStatus.QUEUED,
        models.Document.OcrStatus.PROCESSING,
    ):
        raise PageExtractionFailed(
            "Paper context will be available after OCR finishes.",
            details={"document_id": document_id, "ocr_status": document.ocr_status},
        )
    if (
        document.context_status != "ready"
        or not document.document_hash
        or not document.context_pages.exists()
        or document.context_updated_at is None
        or path.stat().st_mtime > document.context_updated_at.timestamp()
    ):
        ingest_document(document_id)
        document.refresh_from_db()
    return document


def cleanup_stale_context_cache(retention_days: int = 30) -> int:
    root = Path(get_app_data_dir()) / "paper_context"
    if not root.exists():
        return 0
    active_hashes = set(models.Document.objects.exclude(document_hash="").values_list("document_hash", flat=True))
    cutoff = timezone.now() - timedelta(days=retention_days)
    removed = 0
    for child in root.iterdir():
        if child.name in active_hashes:
            continue
        modified = datetime.fromtimestamp(child.stat().st_mtime, tz=timezone.get_current_timezone())
        if modified < cutoff:
            shutil.rmtree(child, ignore_errors=True)
            removed += 1
    return removed


def _clear_fts_index() -> None:
    try:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM api_documentchunk_fts")
    except Exception as exc:
        LOGGER.warning("Could not clear paper-context FTS index: %s", exc)


def _remove_tree(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        path.unlink(missing_ok=True)
        return 1
    removed = sum(1 for child in path.iterdir() if child.is_dir())
    shutil.rmtree(path, ignore_errors=True)
    return max(removed, 1)


def clear_paper_context(*, include_ai_sessions: bool = True) -> dict[str, int]:
    """Delete extracted page context, cached images, and search chunks."""
    page_count = models.DocumentPage.objects.count()
    chunk_count = models.DocumentChunk.objects.count()
    models.DocumentPage.objects.all().delete()
    models.DocumentChunk.objects.all().delete()
    _clear_fts_index()

    documents_reset = models.Document.objects.update(
        context_status="not_started",
        context_error="",
        document_hash="",
        page_count=0,
        context_created_at=None,
        context_updated_at=None,
    )

    app_data = Path(get_app_data_dir())
    cache_dirs_removed = _remove_tree(app_data / "paper_context")
    session_dirs_removed = 0
    if include_ai_sessions:
        session_dirs_removed = _remove_tree(app_data / "ai_sessions")

    return {
        "documents_reset": documents_reset,
        "pages_removed": page_count,
        "chunks_removed": chunk_count,
        "cache_dirs_removed": cache_dirs_removed,
        "session_dirs_removed": session_dirs_removed,
    }
