import re
import urllib.parse
import urllib.request
from functools import lru_cache
from html.parser import HTMLParser

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


class _ArxivPageMetadataParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.metadata: dict[str, str] = {}

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "meta":
            return

        attributes = {str(key).lower(): value for key, value in attrs}
        name = str(attributes.get("name") or "").lower()
        content = str(attributes.get("content") or "").strip()
        if name in {"citation_title", "citation_pdf_url"} and content:
            self.metadata[name] = content


def _metadata_from_abs_page(arxiv_id: str, page_data: bytes) -> dict | None:
    parser = _ArxivPageMetadataParser()
    parser.feed(page_data.decode("utf-8", errors="replace"))

    title = re.sub(r"\s+", " ", parser.metadata.get("citation_title", "")).strip()
    if not title:
        return None

    return {
        "arxiv_id": arxiv_id,
        "title": title,
        # arXiv's citation tag can omit an explicitly requested version. Build
        # the URL from the parsed input so /pdf/...v1 imports that exact version.
        "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
    }


def _fetch_arxiv_api_metadata(arxiv_id: str) -> dict | None:
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


def _fetch_arxiv_abs_metadata(arxiv_id: str) -> dict | None:
    request = urllib.request.Request(
        f"https://arxiv.org/abs/{urllib.parse.quote(arxiv_id)}",
        headers={"User-Agent": ARXIV_USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return _metadata_from_abs_page(arxiv_id, response.read())


@lru_cache(maxsize=256)
def _fetch_arxiv_metadata_cached(arxiv_id: str) -> dict | None:
    """Resolve metadata through the API, falling back to the public abstract page."""
    api_error: Exception | None = None
    try:
        metadata = _fetch_arxiv_api_metadata(arxiv_id)
        if metadata:
            return metadata
    except Exception as exc:
        api_error = exc

    try:
        return _fetch_arxiv_abs_metadata(arxiv_id)
    except Exception:
        if api_error is not None:
            raise api_error
        raise


def fetch_arxiv_metadata(arxiv_id: str) -> dict | None:
    metadata = _fetch_arxiv_metadata_cached(_normalize_arxiv_id(arxiv_id))
    return dict(metadata) if metadata else None
