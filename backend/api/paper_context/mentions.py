from __future__ import annotations

from dataclasses import dataclass, field
import re

from api.errors import ContextLimitExceeded, PageOutOfRange, ResearchMarkerError
from .types import ContextLimits

PAGE_MENTION_RE = re.compile(
    r"@pages?\b(?:[ \t]+(?P<expression>[-+\d,\s\u2013\u2014]+))?",
    re.IGNORECASE,
)
LOCAL_MENTION_RE = re.compile(r"@(selection|current)\b", re.IGNORECASE)
RANGE_RE = re.compile(r"^(-?\d+)\s*[-\u2013\u2014]\s*(-?\d+)$")
INTEGER_RE = re.compile(r"^-?\d+$")


class InvalidMentionSyntax(ResearchMarkerError):
    code = "invalid_mention_syntax"


@dataclass(slots=True)
class MentionResult:
    normalized_question: str
    page_numbers: list[int] = field(default_factory=list)
    uses_selection: bool = False
    uses_current: bool = False
    had_page_mention: bool = False


def _validate_page(page: int, page_count: int) -> None:
    if page < 1 or page > page_count:
        raise PageOutOfRange(
            f"Page {page} is outside this document's page range (1–{page_count}).",
            details={"page_number": page, "page_count": page_count},
        )


def _parse_expression(expression: str, page_count: int) -> list[int]:
    cleaned = expression.strip(" \t\r\n")
    if not cleaned:
        return []
    if cleaned.endswith(",") or ",," in cleaned:
        raise InvalidMentionSyntax(f"Invalid page list: {cleaned!r}.")

    requested: list[int] = []
    for token in cleaned.split(","):
        token = token.strip()
        if not token:
            raise InvalidMentionSyntax(f"Invalid page list: {cleaned!r}.")

        range_match = RANGE_RE.fullmatch(token)
        if range_match:
            start, end = (int(value) for value in range_match.groups())
            _validate_page(start, page_count)
            _validate_page(end, page_count)
            if end < start:
                raise InvalidMentionSyntax(
                    f"Page range {token!r} runs backwards. Use the lower page first."
                )
            requested.extend(range(start, end + 1))
            continue

        if INTEGER_RE.fullmatch(token):
            page = int(token)
            _validate_page(page, page_count)
            requested.append(page)
            continue

        raise InvalidMentionSyntax(
            f"Invalid page expression {token!r}. Use values such as 4, 7-9."
        )
    return requested


def parse_mentions(
    question: str,
    *,
    page_count: int,
    current_page: int | None,
    limits: ContextLimits | None = None,
) -> MentionResult:
    limits = limits or ContextLimits()
    pages: list[int] = []
    seen: set[int] = set()
    had_page_mention = False

    def replace_page(match: re.Match) -> str:
        nonlocal had_page_mention
        had_page_mention = True
        expression = (match.group("expression") or "").strip()
        requested = _parse_expression(expression, page_count) if expression else []
        if not requested:
            if current_page is None:
                raise InvalidMentionSyntax(
                    "Bare @page requires a currently visible page."
                )
            _validate_page(current_page, page_count)
            requested = [current_page]
        for page in requested:
            if page not in seen:
                seen.add(page)
                pages.append(page)
        return " "

    normalized = PAGE_MENTION_RE.sub(replace_page, question)
    uses_selection = bool(re.search(r"@selection\b", normalized, re.IGNORECASE))
    uses_current = bool(re.search(r"@current\b", normalized, re.IGNORECASE))
    normalized = LOCAL_MENTION_RE.sub(" ", normalized)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r" *\n *", "\n", normalized).strip()

    if len(pages) > limits.maximum_explicit_pages:
        raise ContextLimitExceeded(
            (
                f"You requested {len(pages)} pages, but the current limit is "
                f"{limits.maximum_explicit_pages}. Narrow the page range."
            ),
            details={
                "requested_pages": pages,
                "maximum_explicit_pages": limits.maximum_explicit_pages,
            },
        )

    return MentionResult(
        normalized_question=normalized,
        page_numbers=pages,
        uses_selection=uses_selection,
        uses_current=uses_current,
        had_page_mention=had_page_mention,
    )
