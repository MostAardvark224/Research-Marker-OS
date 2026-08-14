from __future__ import annotations

from pathlib import Path
import re

from api.errors import ContextLimitExceeded
from .mentions import InvalidMentionSyntax, parse_mentions
from .retrieval import get_page, search_document, update_active_context
from .types import ContextLimits, PaperContext, SelectionContext

VISUAL_QUESTION_RE = re.compile(
    r"\b(figure|fig\.|table|chart|equation|diagram|layout|image|caption|visual|"
    r"axis|axes|curve|plot|spatial|derive|derivation)\b",
    re.IGNORECASE,
)

PAPER_ANSWER_INSTRUCTIONS = """You are answering a question about the supplied research paper.
Base paper-specific claims only on the supplied context.
Cite support as [p. N] or [pp. N–M], using the application page labels below.
Never invent a page citation or claim to have examined a page that was not supplied.
Distinguish the paper's claims from your interpretation.
If the context is insufficient, say so directly.
When a page image is supplied, describe the visual evidence you used.
Refer to equations, figures, and tables by their printed labels when available.
Page numbers refer to the application labels, not inferred PDF indexes."""


def _image_allowed(path: str | None, limits: ContextLimits, current_count: int) -> bool:
    if not path or current_count >= limits.maximum_page_images:
        return False
    try:
        return Path(path).is_file() and Path(path).stat().st_size <= limits.maximum_image_bytes
    except OSError:
        return False


def _page_needs_image(page, *, visual_question: bool, force: bool) -> bool:
    suspicious = not page.text.strip() or page.source_type == "failed"
    low_confidence = page.ocr_confidence is not None and page.ocr_confidence < 0.75
    return force or page.visually_complex or low_confidence or suspicious or visual_question


def build_paper_context(
    *,
    document_id: int,
    question: str,
    current_page: int | None = None,
    selected_text: str = "",
    selected_text_page: int | None = None,
    include_page_image: bool = False,
    limits: ContextLimits | None = None,
) -> PaperContext:
    from .ingestion import ensure_document_ingested

    limits = limits or ContextLimits()
    document = ensure_document_ingested(document_id)
    mentions = parse_mentions(
        question,
        page_count=document.page_count,
        current_page=current_page,
        limits=limits,
    )
    if not mentions.normalized_question:
        raise InvalidMentionSyntax("Add a question after the context mention.")

    update_active_context(
        document_id=document.id,
        document_title=document.title,
        current_page=current_page,
        selected_text=selected_text,
        selected_text_page=selected_text_page,
    )
    context = PaperContext(
        document_id=document.id,
        document_title=document.title,
        user_question=mentions.normalized_question,
        referenced_pages=list(mentions.page_numbers),
        current_page=current_page,
    )
    visual_question = bool(VISUAL_QUESTION_RE.search(mentions.normalized_question))
    requested_pages = list(mentions.page_numbers)
    if mentions.uses_current and current_page and current_page not in requested_pages:
        requested_pages.append(current_page)
        context.context_reason[f"page:{current_page}"] = "current_page"

    used_characters = 0
    for page_number in requested_pages:
        preview = get_page(document.id, page_number, include_image=False)
        include_image = _page_needs_image(
            preview,
            visual_question=visual_question,
            force=include_page_image,
        )
        page = get_page(
            document.id,
            page_number,
            include_image=include_image,
            reason=(
                "explicit_page_reference"
                if page_number in mentions.page_numbers
                else "current_page"
            ),
        )
        page_chars = len(page.text)
        if used_characters + page_chars > limits.maximum_text_characters:
            raise ContextLimitExceeded(
                "The explicitly requested pages contain too much text. Narrow the page range.",
                details={
                    "maximum_text_characters": limits.maximum_text_characters,
                    "requested_pages": requested_pages,
                },
            )
        used_characters += page_chars
        if page.image_path and _image_allowed(page.image_path, limits, len(context.page_images)):
            context.page_images.append(page.image_path)
            context.context_reason[f"image:{page_number}"] = (
                "figure_request" if visual_question else "visual_page"
            )
        else:
            page.image_path = None
        context.page_text.append(page)
        context.context_reason.setdefault(f"page:{page_number}", page.context_reason)

    if mentions.uses_selection:
        if not selected_text.strip() or selected_text_page is None:
            raise InvalidMentionSyntax("@selection was used, but no PDF text is currently selected.")
        if selected_text_page < 1 or selected_text_page > document.page_count:
            raise InvalidMentionSyntax("The selected text is not associated with a valid page.")
        selection = selected_text.strip()
        remaining = limits.maximum_text_characters - used_characters
        if len(selection) > remaining:
            raise ContextLimitExceeded(
                "The current selection exceeds the configured context limit.",
                details={"maximum_text_characters": limits.maximum_text_characters},
            )
        context.selected_text = SelectionContext(text=selection, page_number=selected_text_page)
        context.context_reason["selection"] = "current_selection"
        used_characters += len(selection)

    if not mentions.had_page_mention:
        chunks = search_document(
            document.id,
            mentions.normalized_question,
            limit=limits.maximum_retrieved_chunks,
        )
        for chunk in chunks:
            remaining = limits.maximum_text_characters - used_characters
            if remaining <= 0:
                break
            if len(chunk.chunk_text) > remaining:
                if remaining < 300:
                    break
                chunk.chunk_text = chunk.chunk_text[:remaining].rsplit(" ", 1)[0] + "…"
            context.retrieved_chunks.append(chunk)
            used_characters += len(chunk.chunk_text)
            context.context_reason[f"chunk:{chunk.chunk_id}"] = "semantic_retrieval"

        if visual_question:
            for chunk in context.retrieved_chunks:
                if len(context.page_images) >= limits.maximum_page_images:
                    break
                if any(page.page_number == chunk.start_page for page in context.page_text):
                    continue
                preview = get_page(document.id, chunk.start_page, include_image=False)
                if not preview.visually_complex:
                    continue
                page = get_page(
                    document.id,
                    chunk.start_page,
                    include_image=True,
                    reason="visual_page",
                )
                if page.image_path and _image_allowed(
                    page.image_path,
                    limits,
                    len(context.page_images),
                ):
                    context.page_images.append(page.image_path)
                    context.page_text.append(page)
                    context.context_reason[f"image:{page.page_number}"] = "visual_page"
        context.retrieval_confidence = "poor" if not context.retrieved_chunks else "high"

    return context


def format_paper_context(context: PaperContext) -> str:
    sections = [
        PAPER_ANSWER_INSTRUCTIONS,
        f"--- DOCUMENT: {context.document_title} ---",
    ]
    for page in context.page_text:
        sections.append(
            f"--- PAGE {page.page_number} ---\n"
            f"[source={page.source_type}; ocr_used={str(page.ocr_used).lower()}]\n"
            f"{page.text or '[No reliable text was extracted from this page.]'}"
        )
    if context.selected_text:
        sections.append(
            f"--- SELECTED TEXT FROM PAGE {context.selected_text.page_number} ---\n"
            f"{context.selected_text.text}"
        )
    for chunk in context.retrieved_chunks:
        label = (
            f"PAGE {chunk.start_page}"
            if chunk.start_page == chunk.end_page
            else f"PAGES {chunk.start_page}–{chunk.end_page}"
        )
        heading = f" ({chunk.section_title})" if chunk.section_title else ""
        sections.append(f"--- RETRIEVED {label}{heading} ---\n{chunk.chunk_text}")
    if context.retrieval_confidence == "poor":
        sections.append(
            "Retrieval confidence is poor; the supplied context may be incomplete. "
            "Do not fill gaps with unsupported document claims."
        )
    sections.append(f"--- USER QUESTION ---\n{context.user_question}")
    return "\n\n".join(sections)
