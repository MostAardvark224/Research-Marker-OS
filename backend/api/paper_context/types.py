from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

ContextReason = Literal[
    "explicit_page_reference",
    "current_page",
    "current_selection",
    "semantic_retrieval",
    "visual_page",
    "figure_request",
]


@dataclass(slots=True)
class ContextLimits:
    maximum_explicit_pages: int = 20
    maximum_retrieved_chunks: int = 6
    maximum_text_characters: int = 48_000
    maximum_page_images: int = 4
    maximum_image_bytes: int = 8 * 1024 * 1024


@dataclass(slots=True)
class PageContext:
    document_id: int
    document_hash: str
    document_title: str
    page_number: int
    text: str
    text_blocks: list[dict]
    source_type: str
    ocr_used: bool
    ocr_confidence: float | None
    visually_complex: bool
    image_path: str | None = None
    context_reason: ContextReason = "explicit_page_reference"

    def to_dict(self, *, expose_local_path: bool = True) -> dict:
        data = asdict(self)
        if not expose_local_path:
            data.pop("image_path", None)
            data["has_image"] = bool(self.image_path)
        return data


@dataclass(slots=True)
class RetrievedChunk:
    document_id: int
    chunk_id: str
    start_page: int
    end_page: int
    chunk_text: str
    section_title: str
    score: float
    context_reason: ContextReason = "semantic_retrieval"


@dataclass(slots=True)
class SelectionContext:
    text: str
    page_number: int
    context_reason: ContextReason = "current_selection"


@dataclass(slots=True)
class PaperContext:
    document_id: int
    document_title: str
    user_question: str
    referenced_pages: list[int] = field(default_factory=list)
    retrieved_chunks: list[RetrievedChunk] = field(default_factory=list)
    current_page: int | None = None
    selected_text: SelectionContext | None = None
    page_text: list[PageContext] = field(default_factory=list)
    page_images: list[str] = field(default_factory=list)
    context_reason: dict[str, ContextReason] = field(default_factory=dict)
    retrieval_confidence: str = "high"

    def to_dict(self, *, expose_local_paths: bool = True) -> dict:
        return {
            "document_id": self.document_id,
            "document_title": self.document_title,
            "user_question": self.user_question,
            "referenced_pages": self.referenced_pages,
            "retrieved_chunks": [asdict(item) for item in self.retrieved_chunks],
            "current_page": self.current_page,
            "selected_text": asdict(self.selected_text) if self.selected_text else None,
            "page_text": [
                page.to_dict(expose_local_path=expose_local_paths) for page in self.page_text
            ],
            "page_images": self.page_images if expose_local_paths else [Path(p).name for p in self.page_images],
            "context_reason": self.context_reason,
            "retrieval_confidence": self.retrieval_confidence,
        }
