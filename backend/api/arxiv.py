import re
import urllib.parse
import urllib.request

import feedparser

ARXIV_URL_PATTERNS = (
    r"arxiv\.org/abs/(?P<id>[^\s?#]+)",
    r"arxiv\.org/pdf/(?P<id>[^\s?#/]+)",
    r"arxiv:(?P<id>\S+)",
)

ARXIV_USER_AGENT = "Research-Marker-OS/1.0 (mailto:support@example.com)"

BARE_ARXIV_ID_PATTERN = re.compile(
    r"^(?:[\w.-]+/[\w.-]+|\d{4}\.\d{4,5})(?:v\d+)?$"
)


def _normalize_arxiv_id(arxiv_id: str) -> str:
    normalized = arxiv_id.rstrip("/")
    if normalized.lower().endswith(".pdf"):
        normalized = normalized[:-4]
    return normalized


def parse_arxiv_id(value: str) -> str | None:
    value = (value or "").strip()
    if not value:
        return None

    for pattern in ARXIV_URL_PATTERNS:
        match = re.search(pattern, value, re.IGNORECASE)
        if match:
            return _normalize_arxiv_id(match.group("id"))

    if BARE_ARXIV_ID_PATTERN.match(value):
        return value

    return None


def _entry_pdf_url(entry) -> str:
    for link in entry.links:
        if link.rel == "related" and link.type == "application/pdf":
            return link.href

    entry_id = str(entry.get("id", ""))
    return entry_id.replace("/abs/", "/pdf/")


def fetch_arxiv_metadata(arxiv_id: str) -> dict | None:
    encoded_id = urllib.parse.quote(arxiv_id)
    query_url = (
        f"https://export.arxiv.org/api/query?id_list={encoded_id}&max_results=1"
    )

    request = urllib.request.Request(
        query_url,
        headers={"User-Agent": ARXIV_USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        feed_data = response.read()

    feed = feedparser.parse(feed_data)
    if not feed.entries:
        return None

    entry = feed.entries[0]
    entry_id = str(entry.get("id", ""))
    resolved_id = entry_id.split("/abs/")[-1]
    title = re.sub(r"\s+", " ", str(entry.get("title", ""))).strip()

    return {
        "arxiv_id": resolved_id,
        "title": title,
        "pdf_url": _entry_pdf_url(entry),
    }
