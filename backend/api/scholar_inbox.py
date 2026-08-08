"""Scholar Inbox: Gmail Alert Digest → arXiv PDF import."""

from __future__ import annotations

import email
import imaplib
import re
import time
import urllib.parse
import urllib.request
from typing import Any

import feedparser
from bs4 import BeautifulSoup

# DEBUGGING: If scraping isn't working, first suspect is the CSS selectors or Regex used to find elements.
# Do control-F in this file and search for "NOTE TO USER" comments for places where selectors may need to be updated.

DOCUMENT_TITLE_MAX_LENGTH = 255
ARXIV_QUERY_DELAY_SECONDS = 0.35


class ScholarInboxError(Exception):
    """Raised for actionable Scholar Inbox failures (credentials, IMAP, parse)."""

    def __init__(self, message: str, *, code: str = "error", http_status: int = 502):
        super().__init__(message)
        self.message = message
        self.code = code
        self.http_status = http_status


def _decode_html_payload(part) -> str:
    payload = part.get_payload(decode=True)
    if not isinstance(payload, bytes):
        return ""
    charset = part.get_content_charset() or "utf-8"
    return payload.decode(charset, errors="ignore")


def _close_mail_connection(mail):
    try:
        mail.close()
    except Exception:
        pass
    try:
        mail.logout()
    except Exception:
        pass


def _normalize_amount(amount_of_papers):
    """Return a positive int limit, or None to import all papers in the digest."""
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


def _normalize_gmail_app_password(password: str) -> str:
    # Google shows app passwords as "xxxx xxxx xxxx xxxx"; IMAP wants no spaces.
    return re.sub(r"\s+", "", str(password or "").strip())


def _truncate_title(title: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(title or "").strip())
    if len(cleaned) <= DOCUMENT_TITLE_MAX_LENGTH:
        return cleaned
    return cleaned[: DOCUMENT_TITLE_MAX_LENGTH - 1].rstrip() + "…"


def _extract_paper_links(soup: BeautifulSoup) -> list[dict[str, str]]:
    # NOTE TO USER: Primary selector looks for <a> tags where href contains
    # "scholar-inbox.com/login". Fallbacks cover minor template changes.
    candidates = soup.find_all("a", href=re.compile(r"scholar-inbox\.com/login", re.I))
    if not candidates:
        candidates = soup.find_all("a", href=re.compile(r"scholar-inbox\.com", re.I))

    extracted: list[dict[str, str]] = []
    for link in candidates:
        title = _truncate_title(link.get_text(" ", strip=True))
        href = (link.get("href") or "").strip()
        if not title or not href:
            continue
        # Skip obvious non-paper chrome links.
        lowered = title.lower()
        if lowered in {"scholar inbox", "unsubscribe", "view in browser", "login"}:
            continue
        extracted.append({"title": title, "scraped_url": href})

    seen_titles: set[str] = set()
    unique_papers: list[dict[str, str]] = []
    for paper in extracted:
        if paper["title"] in seen_titles:
            continue
        seen_titles.add(paper["title"])
        unique_papers.append(paper)
    return unique_papers


def _resolve_arxiv_pdf(paper: dict[str, Any]) -> dict[str, Any] | None:
    encoded_title = urllib.parse.quote(f'ti:"{paper["title"]}"')
    query_url = (
        "http://export.arxiv.org/api/query?"
        f"search_query={encoded_title}&max_results=1"
    )

    with urllib.request.urlopen(query_url, timeout=30) as response:
        feed_data = response.read()

    feed = feedparser.parse(feed_data)
    if not feed.entries:
        return None

    entry = feed.entries[0]
    entry_id = str(entry.get("id", ""))
    arxiv_id = entry_id.split("/abs/")[-1]

    pdf_url = None
    for link in getattr(entry, "links", []) or []:
        if getattr(link, "rel", None) == "related" and getattr(link, "type", None) == "application/pdf":
            pdf_url = link.href
            break

    if not pdf_url and entry_id:
        pdf_url = entry_id.replace("/abs/", "/pdf/")

    if not pdf_url:
        return None

    resolved = dict(paper)
    resolved["id"] = arxiv_id
    resolved["pdf_url"] = pdf_url
    return resolved


def fetch_scholar_inbox_papers(env_vars, amount_of_papers=None) -> dict[str, Any]:
    """
    Fetch the latest Scholar Inbox Alert Digest and resolve arXiv PDF URLs.

    Returns a result dict:
      {
        "papers": [...],
        "unmatched_titles": [...],
        "digest_found": bool,
        "titles_found": int,
      }

    Raises ScholarInboxError for credentials / IMAP / email-body failures.
    """
    email_addr = str(env_vars.get("scholar_inbox_email", "")).strip()
    password = _normalize_gmail_app_password(env_vars.get("gmail_app_password", ""))

    if not email_addr or not password:
        raise ScholarInboxError(
            "Scholar Inbox Gmail credentials are not configured. "
            "Set Scholar Inbox Email and Gmail App Password in Settings → General.",
            code="credentials_missing",
            http_status=400,
        )

    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    try:
        try:
            mail.login(email_addr, password)
        except imaplib.IMAP4.error as exc:
            raise ScholarInboxError(
                "Gmail IMAP login failed. Check that IMAP is enabled and you are using "
                f"a Google App Password (not your normal password). Details: {exc}",
                code="imap_login_failed",
                http_status=401,
            ) from exc

        status, _ = mail.select("INBOX", readonly=True)
        if status != "OK":
            raise ScholarInboxError(
                "Could not open the Gmail inbox over IMAP.",
                code="imap_select_failed",
                http_status=502,
            )

        print("Searching for Alert Digest email...")
        search_criteria = '(FROM "noreply@cvlibs.net" SUBJECT "Alert Digest")'
        status, data = mail.search(None, search_criteria)

        if status != "OK" or not data or not data[0]:
            return {
                "papers": [],
                "unmatched_titles": [],
                "digest_found": False,
                "titles_found": 0,
            }

        mail_ids = data[0].split()
        if not mail_ids:
            return {
                "papers": [],
                "unmatched_titles": [],
                "digest_found": False,
                "titles_found": 0,
            }

        latest_id = mail_ids[-1]
        status, data = mail.fetch(latest_id, "(RFC822)")
        if status != "OK" or not data or not data[0]:
            raise ScholarInboxError(
                "Found an Alert Digest email but failed to download it.",
                code="imap_fetch_failed",
                http_status=502,
            )

        fetch_result = data[0]
        if not isinstance(fetch_result, tuple) or len(fetch_result) < 2:
            raise ScholarInboxError(
                "Unexpected Gmail IMAP response while reading the Alert Digest.",
                code="imap_fetch_invalid",
                http_status=502,
            )

        raw_email = fetch_result[1]
        if not isinstance(raw_email, bytes):
            raise ScholarInboxError(
                "Alert Digest email body was unreadable.",
                code="email_body_invalid",
                http_status=502,
            )

        msg = email.message_from_bytes(raw_email)

        html_content = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    html_content = _decode_html_payload(part)
                    if html_content:
                        break
        elif msg.get_content_type() == "text/html":
            html_content = _decode_html_payload(msg)

        if not html_content:
            raise ScholarInboxError(
                "The latest Alert Digest email had no HTML body to parse.",
                code="email_html_missing",
                http_status=502,
            )

        soup = BeautifulSoup(html_content, "html.parser")
        unique_papers = _extract_paper_links(soup)

        paper_limit = _normalize_amount(amount_of_papers)
        if paper_limit is not None:
            unique_papers = unique_papers[:paper_limit]

        print(
            f"Found {len(unique_papers)} unique papers in the email. "
            "Searching arXiv API by title..."
        )

        arxiv_links: list[dict[str, Any]] = []
        unmatched_titles: list[str] = []
        for index, paper in enumerate(unique_papers):
            if index > 0:
                time.sleep(ARXIV_QUERY_DELAY_SECONDS)
            try:
                resolved = _resolve_arxiv_pdf(paper)
            except Exception as exc:
                print(f"Error querying arXiv for '{paper['title']}': {exc}")
                unmatched_titles.append(paper["title"])
                continue

            if resolved:
                arxiv_links.append(resolved)
            else:
                print(f"Could not find arXiv match for: {paper['title']}")
                unmatched_titles.append(paper["title"])

        print(f"Returning {len(arxiv_links)} papers with PDF URLs.")
        return {
            "papers": arxiv_links,
            "unmatched_titles": unmatched_titles,
            "digest_found": True,
            "titles_found": len(unique_papers),
        }
    except ScholarInboxError:
        raise
    except Exception as exc:
        raise ScholarInboxError(
            f"Unexpected Scholar Inbox error: {exc}",
            code="unexpected_error",
            http_status=500,
        ) from exc
    finally:
        _close_mail_connection(mail)
