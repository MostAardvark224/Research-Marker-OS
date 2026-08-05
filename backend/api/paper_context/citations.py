from __future__ import annotations

from dataclasses import asdict, dataclass
import re

CITATION_RE = re.compile(
    r"\[(?P<label>p{1,2}\.)\s*(?P<start>\d+)(?:\s*[\-\u2013\u2014]\s*(?P<end>\d+))?\]",
    re.IGNORECASE,
)


@dataclass(slots=True)
class Citation:
    document_id: int
    page_start: int
    page_end: int
    quoted_or_paraphrased_text: str
    valid: bool

    def to_dict(self) -> dict:
        return asdict(self)


def extract_citations(
    answer: str,
    *,
    document_id: int,
    allowed_pages: set[int],
) -> list[Citation]:
    citations: list[Citation] = []
    seen: set[tuple[int, int, str]] = set()
    for match in CITATION_RE.finditer(answer or ""):
        start = int(match.group("start"))
        end = int(match.group("end") or start)
        sentence_start = max(
            answer.rfind(".", 0, match.start()),
            answer.rfind("\n", 0, match.start()),
        )
        sentence_end = answer.find(".", match.end())
        if sentence_end < 0:
            sentence_end = min(len(answer), match.end() + 220)
        context = answer[sentence_start + 1 : sentence_end + 1].strip()
        valid = end >= start and all(page in allowed_pages for page in range(start, end + 1))
        key = (start, end, context)
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            Citation(
                document_id=document_id,
                page_start=start,
                page_end=end,
                quoted_or_paraphrased_text=context,
                valid=valid,
            )
        )
    return citations
