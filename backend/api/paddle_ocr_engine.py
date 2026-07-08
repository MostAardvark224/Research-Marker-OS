"""Bundled PaddleOCR (PP-OCRv4) local inference.

The official ``paddleocr`` Python package requires the full PaddlePaddle
framework (~500MB+), which is impractical to bundle in a desktop app. Instead
we ship the official PaddleOCR ONNX exports in ``backend/ocr_models/`` and run
them with ONNX Runtime.

The ``rapidocr_onnxruntime`` package implements PaddleOCR's PP-OCR pipeline
(``ch_ppocr_det``, ``ch_ppocr_cls``, ``ch_ppocr_rec``) without PaddlePaddle.
This is the same model family and quality as PaddleOCR local inference.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from django.conf import settings
from rapidocr_onnxruntime import RapidOCR

_OCR_ENGINE: RapidOCR | None = None


class PaddleOCREngineError(Exception):
    pass


def get_model_path(filename: str) -> str:
    if getattr(sys, "frozen", False):
        bundle_dir = Path(getattr(sys, "_MEIPASS", "."))
        return os.path.join(bundle_dir, "ocr_models", filename)
    return os.path.join(settings.BASE_DIR, "ocr_models", filename)


def _validate_bundled_models() -> None:
    required = [
        "ch_PP-OCRv4_det_infer.onnx",
        "ch_ppocr_mobile_v2.0_cls_infer.onnx",
        "ch_PP-OCRv4_rec_infer.onnx",
        "ppocr_keys_v1.txt",
    ]
    missing = [name for name in required if not os.path.isfile(get_model_path(name))]
    if missing:
        raise PaddleOCREngineError(
            "Bundled PaddleOCR model files are missing: " + ", ".join(missing)
        )


def get_paddle_ocr_engine() -> RapidOCR:
    global _OCR_ENGINE
    if _OCR_ENGINE is None:
        _validate_bundled_models()
        print("Loading bundled PaddleOCR PP-OCRv4 ONNX models")
        _OCR_ENGINE = RapidOCR(
            det_model_path=get_model_path("ch_PP-OCRv4_det_infer.onnx"),
            cls_model_path=get_model_path("ch_ppocr_mobile_v2.0_cls_infer.onnx"),
            rec_model_path=get_model_path("ch_PP-OCRv4_rec_infer.onnx"),
            rec_keys_path=get_model_path("ppocr_keys_v1.txt"),
        )
    return _OCR_ENGINE


def run_paddle_ocr_on_image(img_bytes: bytes) -> list[list[Any]]:
    """Run bundled PaddleOCR on PNG/JPEG bytes. Returns detection rows or []."""
    engine = get_paddle_ocr_engine()
    ocr_result, _elapsed = engine(img_bytes)
    return ocr_result or []
