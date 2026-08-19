"""Scholar Inbox API digest -> arXiv PDF import."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from api.arxiv import parse_arxiv_id

DOCUMENT_TITLE_MAX_LENGTH = 255
SCHOLAR_INBOX_API_URL = "https://api.scholar-inbox.com/v1/digest"
SCHOLAR_INBOX_API_MAX_PAPERS = 100
SCHOLAR_INBOX_USER_AGENT = "Research-Marker-OS/1.0"


class ScholarInboxError(Exception):
    """Raised for actionable Scholar Inbox API failures."""

    def __init__(self, message: str, *, code: str = "error", http_status: int = 502):
        super().__init__(message)
        self.message = message
        self.code = code
        self.http_status = http_status


def _normalize_amount(amount_of_papers):
    """Return a positive int limit, or None to import all available papers."""
    if amount_of_papers is None:
        return None

    if isinstance(amount_of_papers, str):
        normalized = amount_of_papers.strip().lower()
        if normalized in ("all", ""):
            return None
        if normalized.isdigit():
            value = int(normalized)
            return value if value > 0 else None
        return None

    if isinstance(amount_of_papers, int) and amount_of_papers > 0:
        return amount_of_papers

    return None


def _api_paper_limit(amount_of_papers) -> int:
    requested = _normalize_amount(amount_of_papers)
    if requested is None:
        return SCHOLAR_INBOX_API_MAX_PAPERS
    return min(requested, SCHOLAR_INBOX_API_MAX_PAPERS)


def _truncate_title(title: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(title or "").strip())
    if len(cleaned) <= DOCUMENT_TITLE_MAX_LENGTH:
        return cleaned
    return cleaned[: DOCUMENT_TITLE_MAX_LENGTH - 1].rstrip() + "…"


def _arxiv_pdf_url(url: str) -> tuple[str, str] | None:
    """Build a canonical arXiv PDF URL from the digest paper's url field."""
    arxiv_id = parse_arxiv_id(str(url or ""))
    if not arxiv_id:
        return None
    return arxiv_id, f"https://arxiv.org/pdf/{arxiv_id}.pdf"


def _request_digest(api_key: str, top_k: int) -> dict[str, Any]:
    query = urllib.parse.urlencode({"top_k": top_k})
    request = urllib.request.Request(
        f"{SCHOLAR_INBOX_API_URL}?{query}",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": SCHOLAR_INBOX_USER_AGENT,
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise ScholarInboxError(
                "Scholar Inbox rejected the API key. Check the key in "
                "Settings → Scholar Inbox.",
                code="api_auth_failed",
                http_status=401,
            ) from exc
        if exc.code == 429:
            raise ScholarInboxError(
                "Scholar Inbox API rate limit reached. Try again later.",
                code="api_rate_limited",
                http_status=429,
            ) from exc
        raise ScholarInboxError(
            f"Scholar Inbox API request failed with status {exc.code}.",
            code="api_request_failed",
            http_status=502,
        ) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        reason = getattr(exc, "reason", exc)
        raise ScholarInboxError(
            f"Could not connect to the Scholar Inbox API: {reason}",
            code="api_unavailable",
            http_status=502,
        ) from exc
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as exc:
        raise ScholarInboxError(
            "Scholar Inbox API returned an unreadable response.",
            code="api_response_invalid",
            http_status=502,
        ) from exc

    if not isinstance(payload, dict) or payload.get("success") is not True:
        raise ScholarInboxError(
            "Scholar Inbox API returned an unsuccessful response.",
            code="api_response_invalid",
            http_status=502,
        )
    if not isinstance(payload.get("papers"), list):
        raise ScholarInboxError(
            "Scholar Inbox API response did not include a paper list.",
            code="api_response_invalid",
            http_status=502,
        )
    return payload


def fetch_scholar_inbox_papers(env_vars, amount_of_papers=None) -> dict[str, Any]:
    """Fetch the latest digest through the Scholar Inbox API."""
    api_key = str(env_vars.get("SCHOLAR_INBOX_API_KEY") or "").strip()
    if not api_key:
        raise ScholarInboxError(
            "Scholar Inbox API key is not configured. Find it in Scholar Inbox "
            "Settings, then add it in Settings → Scholar Inbox.",
            code="credentials_missing",
            http_status=400,
        )

    try:
        payload = _request_digest(api_key, _api_paper_limit(amount_of_papers))
        digest_papers = payload["papers"]
        resolved_papers: list[dict[str, Any]] = []
        unmatched_titles: list[str] = []

        for paper in digest_papers:
            if not isinstance(paper, dict):
                continue

            fallback_title = f"Scholar Inbox paper {paper.get('paper_id', '')}".strip()
            title = _truncate_title(paper.get("title") or fallback_title)
            resolved_url = _arxiv_pdf_url(paper.get("url") or "")
            if not resolved_url:
                unmatched_titles.append(title)
                continue

            arxiv_id, pdf_url = resolved_url
            resolved_papers.append(
                {
                    "id": paper.get("arxiv_id") or arxiv_id,
                    "title": title,
                    "pdf_url": pdf_url,
                    "source_url": paper.get("url"),
                }
            )

        return {
            "papers": resolved_papers,
            "unmatched_titles": unmatched_titles,
            "digest_found": bool(digest_papers),
            "titles_found": len(digest_papers),
        }
    except ScholarInboxError:
        raise
    except Exception as exc:
        raise ScholarInboxError(
            f"Unexpected Scholar Inbox error: {exc}",
            code="unexpected_error",
            http_status=500,
        ) from exc
