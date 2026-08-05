"""OCR orchestration for searchable PDF generation.

Local OCR uses bundled PaddleOCR PP-OCRv4 ONNX models (see ``paddle_ocr_engine``).
Cloud OCR uses user-provided API keys (BYOK).
"""

from __future__ import annotations

import base64
import gc
import os
import shutil
from typing import Any

import fitz
import requests
from django.utils import timezone
from django_q.tasks import async_task

from api.paddle_ocr_engine import PaddleOCREngineError, run_paddle_ocr_on_image
from api.utils import load_env_vars

OCR_RENDER_SCALE = 2
OCR_PROVIDER_CONFIG: dict[str, dict[str, Any]] = {
    "paddleocr": {
        "id": "paddleocr",
        "label": "PaddleOCR Local",
        "kind": "local",
        "description": "Bundled PaddleOCR PP-OCRv4 ONNX models. Runs fully on-device.",
        "api_key_env": None,
        "default_model": "PP-OCRv4",
    },
    "mistral": {
        "id": "mistral",
        "label": "Mistral OCR",
        "kind": "byok",
        "description": "Mistral's document OCR API.",
        "api_key_env": "MISTRAL_API_KEY",
        "default_model": "mistral-ocr-latest",
    },
    "openai": {
        "id": "openai",
        "label": "OpenAI Vision",
        "kind": "byok",
        "description": "OpenAI vision model OCR over rendered PDF pages.",
        "api_key_env": "OPENAI_API_KEY",
        "default_model": "gpt-4o-mini",
    },
    "gemini": {
        "id": "gemini",
        "label": "Gemini Vision",
        "kind": "byok",
        "description": "Gemini vision OCR over rendered PDF pages.",
        "api_key_env": "GEMINI_API_KEY",
        "default_model": "gemini-flash-latest",
    },
}


class OCRError(Exception):
    pass


def _queue_context_ingestion(document) -> None:
    document.context_status = "queued"
    document.context_error = ""
    document.save(update_fields=["context_status", "context_error"])
    async_task("api.paper_context.ingestion.ingest_document", document.pk)


def normalize_ocr_provider(provider: str | None) -> str:
    normalized = str(provider or "paddleocr").strip().lower()
    return normalized if normalized in OCR_PROVIDER_CONFIG else "paddleocr"


def get_ocr_providers(env_vars_override: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    env_vars = env_vars_override if env_vars_override is not None else load_env_vars()
    providers: list[dict[str, Any]] = []
    for provider in OCR_PROVIDER_CONFIG.values():
        api_key_env = provider["api_key_env"]
        providers.append(
            {
                **provider,
                "has_api_key": True if api_key_env is None else bool(env_vars.get(api_key_env, "")),
            }
        )
    return providers


def _request_json(method: str, url: str, **kwargs: Any) -> dict[str, Any]:
    timeout = kwargs.pop("timeout", (20, 180))
    try:
        response = requests.request(method, url, timeout=timeout, **kwargs)
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as exc:
        http_response = exc.response
        detail: Any = ""
        if http_response is not None:
            try:
                detail = http_response.json()
            except Exception:
                detail = http_response.text[:500]
        raise OCRError(f"OCR provider request failed: {detail}") from exc
    except requests.RequestException as exc:
        raise OCRError(f"OCR provider request failed: {exc}") from exc


def _render_page_png_bytes(page: fitz.Page) -> bytes:
    pix = page.get_pixmap(matrix=fitz.Matrix(OCR_RENDER_SCALE, OCR_RENDER_SCALE))
    try:
        return pix.tobytes("png")
    finally:
        del pix


def _insert_hidden_page_text(page: fitz.Page, text: str) -> None:
    if not text:
        return
    # Cloud OCR providers generally return page text, not PDF coordinate boxes.
    # Insert it invisibly over the page so search/select works without altering the visual PDF.
    safe_text = str(text).replace("\x00", " ").strip()
    page.insert_textbox(
        page.rect + (8, 8, -8, -8),
        safe_text,
        fontsize=4,
        render_mode=3,
        overlay=True,
    )


def _save_output_doc(input_path: str, output_path: str, page_texts: list[str]) -> None:
    temp_output_path = output_path + ".tmp"
    doc: fitz.Document | None = None
    output_doc: fitz.Document | None = None
    try:
        doc = fitz.open(input_path)
        output_doc = fitz.open()

        for page_num, page in enumerate(doc):
            new_page = output_doc.new_page(width=page.rect.width, height=page.rect.height)
            new_page.show_pdf_page(new_page.rect, doc, page_num)
            _insert_hidden_page_text(new_page, page_texts[page_num] if page_num < len(page_texts) else "")
            page.clean_contents()

        output_doc.save(temp_output_path)
        output_doc.close()
        output_doc = None
        doc.close()
        doc = None
        shutil.move(temp_output_path, output_path)
    finally:
        if output_doc is not None:
            output_doc.close()
        if doc is not None:
            doc.close()
        if os.path.exists(temp_output_path):
            os.remove(temp_output_path)
        gc.collect()


def create_searchable_pdf_with_paddleocr(input_path: str, output_path: str) -> None:
    temp_output_path = output_path + ".tmp"
    doc: fitz.Document | None = None
    output_doc: fitz.Document | None = None

    try:
        doc = fitz.open(input_path)
        output_doc = fitz.open()

        for page_num, page in enumerate(doc):
            pix = None
            img_bytes = None
            try:
                pix = page.get_pixmap(matrix=fitz.Matrix(OCR_RENDER_SCALE, OCR_RENDER_SCALE))
                img_bytes = pix.tobytes("png")
                ocr_result = run_paddle_ocr_on_image(img_bytes)

                new_page = output_doc.new_page(width=page.rect.width, height=page.rect.height)
                new_page.show_pdf_page(new_page.rect, doc, page_num)

                if ocr_result:
                    scale_x = page.rect.width / pix.width
                    scale_y = page.rect.height / pix.height

                    for item in ocr_result:
                        box_points, text, _confidence = item
                        xs = [pt[0] for pt in box_points]
                        ys = [pt[1] for pt in box_points]
                        x_min, y_min = min(xs) * scale_x, min(ys) * scale_y
                        x_max, y_max = max(xs) * scale_x, max(ys) * scale_y
                        new_page.insert_text(
                            fitz.Rect(x_min, y_min, x_max, y_max).tl,
                            text,
                            fontsize=max(y_max - y_min, 4),
                            render_mode=3,
                        )
            finally:
                del img_bytes
                del pix
                page.clean_contents()
                gc.collect()

        output_doc.save(temp_output_path)
        output_doc.close()
        output_doc = None
        doc.close()
        doc = None
        shutil.move(temp_output_path, output_path)
    except PaddleOCREngineError as exc:
        raise OCRError(str(exc)) from exc
    finally:
        if output_doc is not None:
            output_doc.close()
        if doc is not None:
            doc.close()
        if os.path.exists(temp_output_path):
            os.remove(temp_output_path)
        gc.collect()


def _ocr_pdf_with_openai(input_path: str, output_path: str, api_key: str, model: str) -> None:
    page_texts: list[str] = []
    doc = fitz.open(input_path)
    try:
        for page_number, page in enumerate(doc, start=1):
            image_b64 = base64.b64encode(_render_page_png_bytes(page)).decode("utf-8")
            data = _request_json(
                "POST",
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "temperature": 0,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": (
                                        f"Transcribe all visible text on PDF page {page_number}. "
                                        "Return only the OCR text."
                                    ),
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                                },
                            ],
                        }
                    ],
                },
            )
            page_texts.append(data["choices"][0]["message"]["content"])
    finally:
        doc.close()
    _save_output_doc(input_path, output_path, page_texts)


def _ocr_pdf_with_gemini(input_path: str, output_path: str, api_key: str, model: str) -> None:
    page_texts: list[str] = []
    doc = fitz.open(input_path)
    try:
        for page_number, page in enumerate(doc, start=1):
            image_b64 = base64.b64encode(_render_page_png_bytes(page)).decode("utf-8")
            data = _request_json(
                "POST",
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [
                        {
                            "parts": [
                                {
                                    "text": (
                                        f"Transcribe all visible text on PDF page {page_number}. "
                                        "Return only the OCR text."
                                    )
                                },
                                {"inline_data": {"mime_type": "image/png", "data": image_b64}},
                            ]
                        }
                    ],
                    "generationConfig": {"temperature": 0},
                },
            )
            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            page_texts.append("\n".join(part.get("text", "") for part in parts).strip())
    finally:
        doc.close()
    _save_output_doc(input_path, output_path, page_texts)


def _ocr_pdf_with_mistral(input_path: str, output_path: str, api_key: str, model: str) -> None:
    headers = {"Authorization": f"Bearer {api_key}"}
    upload_response: requests.Response | None = None
    try:
        with open(input_path, "rb") as pdf_file:
            upload_response = requests.post(
                "https://api.mistral.ai/v1/files",
                headers=headers,
                data={"purpose": "ocr"},
                files={"file": (os.path.basename(input_path), pdf_file, "application/pdf")},
                timeout=(20, 180),
            )
            upload_response.raise_for_status()
            file_id = upload_response.json()["id"]

        signed_url = _request_json(
            "GET",
            f"https://api.mistral.ai/v1/files/{file_id}/url?expiry=24",
            headers=headers,
        ).get("url")
        if not signed_url:
            raise OCRError("Mistral did not return a signed document URL.")

        ocr_response = _request_json(
            "POST",
            "https://api.mistral.ai/v1/ocr",
            headers={**headers, "Content-Type": "application/json"},
            json={
                "model": model,
                "document": {"type": "document_url", "document_url": signed_url},
                "include_image_base64": False,
            },
            timeout=(20, 300),
        )
    except requests.HTTPError as exc:
        http_response = exc.response or upload_response
        detail = http_response.text[:500] if http_response is not None else str(exc)
        raise OCRError(f"Mistral OCR request failed: {detail}") from exc
    except requests.RequestException as exc:
        raise OCRError(f"Mistral OCR request failed: {exc}") from exc

    pages = ocr_response.get("pages") or []
    page_texts = [page.get("markdown") or page.get("text") or "" for page in pages]
    if not page_texts:
        raise OCRError("Mistral OCR returned no page text.")
    _save_output_doc(input_path, output_path, page_texts)


def create_searchable_pdf(
    input_path: str,
    output_path: str,
    provider: str = "paddleocr",
    model: str | None = None,
) -> str:
    if not os.path.isfile(input_path):
        raise OCRError("Input PDF file was not found.")

    env_vars = load_env_vars()
    provider = normalize_ocr_provider(provider)
    provider_config = OCR_PROVIDER_CONFIG[provider]
    model = model or provider_config["default_model"]

    if provider == "paddleocr":
        create_searchable_pdf_with_paddleocr(input_path, output_path)
        return "success"

    api_key_env = provider_config["api_key_env"]
    api_key = env_vars.get(api_key_env, "") if api_key_env else ""
    if not api_key:
        raise OCRError(f"{provider_config['label']} API key is not configured in Settings.")

    if provider == "openai":
        _ocr_pdf_with_openai(input_path, output_path, api_key, model)
    elif provider == "gemini":
        _ocr_pdf_with_gemini(input_path, output_path, api_key, model)
    elif provider == "mistral":
        _ocr_pdf_with_mistral(input_path, output_path, api_key, model)
    else:
        raise OCRError(f"Unsupported OCR provider: {provider}")

    return "success"


def create_searchable_document_pdf(document_id: int, provider: str | None = None, model: str | None = None) -> str:
    from api import models

    try:
        document = models.Document.objects.get(pk=document_id)
    except models.Document.DoesNotExist:
        print(f"OCR skipped: document {document_id} no longer exists.")
        return "missing"

    provider = normalize_ocr_provider(provider or document.ocr_provider)
    document.ocr_provider = provider
    document.ocr_status = models.Document.OcrStatus.PROCESSING
    document.ocr_error = ""
    document.ocr_started_at = timezone.now()
    document.ocr_completed_at = None
    document.searchable = False
    document.save(
        update_fields=[
            "ocr_provider",
            "ocr_status",
            "ocr_error",
            "ocr_started_at",
            "ocr_completed_at",
            "searchable",
        ]
    )

    if not document.file:
        document.ocr_status = models.Document.OcrStatus.FAILED
        document.ocr_error = "Document has no file."
        document.ocr_completed_at = timezone.now()
        document.save(update_fields=["ocr_status", "ocr_error", "ocr_completed_at"])
        return "missing-file"

    try:
        create_searchable_pdf(document.file.path, document.file.path, provider=provider, model=model)
    except OCRError as exc:
        error_message = str(exc) or exc.__class__.__name__
        print(f"OCR failed for document {document_id}: {error_message}")
        document.ocr_status = models.Document.OcrStatus.FAILED
        document.ocr_error = error_message[:2000]
        document.ocr_completed_at = timezone.now()
        document.save(update_fields=["ocr_status", "ocr_error", "ocr_completed_at"])
        _queue_context_ingestion(document)
        return "failed"
    except Exception as exc:
        error_message = str(exc) or exc.__class__.__name__
        print(f"OCR failed for document {document_id}: {error_message}")
        document.ocr_status = models.Document.OcrStatus.FAILED
        document.ocr_error = error_message[:2000]
        document.ocr_completed_at = timezone.now()
        document.save(update_fields=["ocr_status", "ocr_error", "ocr_completed_at"])
        _queue_context_ingestion(document)
        return "failed"

    document.searchable = True
    document.ocr_status = models.Document.OcrStatus.SUCCEEDED
    document.ocr_error = ""
    document.ocr_completed_at = timezone.now()
    document.save(update_fields=["searchable", "ocr_status", "ocr_error", "ocr_completed_at"])
    _queue_context_ingestion(document)
    return "success"
