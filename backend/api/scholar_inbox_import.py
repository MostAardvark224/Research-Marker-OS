"""Import Scholar Inbox digests into the library (shared by API view + auto-import worker)."""

from __future__ import annotations

from datetime import date
from typing import Any

from django_q.tasks import async_task

from api import models
from api.OCR import normalize_ocr_provider
from api.scholar_inbox import ScholarInboxError, _truncate_title, fetch_scholar_inbox_papers
from api.user_preferences import load_user_preferences, write_user_preferences
from api.utils import load_env_vars


def _stamp_last_import_date() -> None:
    prefs = load_user_preferences()
    user_data = prefs.get("user_preferences", {})
    scholar_prefs = user_data.get("scholar_inbox", {})
    if not isinstance(scholar_prefs, dict):
        scholar_prefs = {}
    scholar_prefs["last_import_date"] = date.today().isoformat()
    user_data["scholar_inbox"] = scholar_prefs
    prefs["user_preferences"] = user_data
    write_user_preferences(prefs)


def import_scholar_inbox_papers(
    amount_to_import="All",
    *,
    skip_ocr: bool = True,
    ocr_provider: str = "paddleocr",
) -> dict[str, Any]:
    """
    Fetch digest papers and create Document rows in the Scholar Inbox folder.

    Raises ScholarInboxError for hard failures (credentials, IMAP, unreadable email).
    """
    # Local import avoids circular imports with views helpers.
    from api.views import _apply_ocr_settings_to_document, _stream_pdf_to_document

    env_vars = load_env_vars()
    fetch_result = fetch_scholar_inbox_papers(env_vars, amount_to_import)

    papers = fetch_result.get("papers") or []
    unmatched_titles = fetch_result.get("unmatched_titles") or []
    digest_found = bool(fetch_result.get("digest_found"))
    titles_found = int(fetch_result.get("titles_found") or 0)

    if not digest_found:
        return {
            "ok": True,
            "digest_found": False,
            "imported": 0,
            "skipped": 0,
            "unmatched": 0,
            "titles_found": 0,
            "message": (
                "No Scholar Inbox Alert Digest emails were found. "
                "Make sure digests from noreply@cvlibs.net are arriving in this Gmail inbox."
            ),
            "should_stamp_daily": False,
        }

    if titles_found == 0:
        return {
            "ok": True,
            "digest_found": True,
            "imported": 0,
            "skipped": 0,
            "unmatched": 0,
            "titles_found": 0,
            "message": (
                "Found an Alert Digest email, but no paper links could be parsed from it. "
                "The email format may have changed."
            ),
            "should_stamp_daily": True,
        }

    if not papers:
        unmatched_count = len(unmatched_titles)
        return {
            "ok": True,
            "digest_found": True,
            "imported": 0,
            "skipped": 0,
            "unmatched": unmatched_count,
            "titles_found": titles_found,
            "message": (
                f"Found {titles_found} paper title(s) in the digest, but none matched on arXiv. "
                "Scholar Inbox import currently supports arXiv papers only."
            ),
            "should_stamp_daily": True,
            "unmatched_titles": unmatched_titles[:20],
        }

    folder, _created = models.Folder.objects.get_or_create(
        name="Scholar Inbox",
        parent=None,
        defaults={"sort_order": 0},
    )

    existing_titles = set(
        models.Document.objects.filter(folder=folder).values_list("title", flat=True)
    )

    provider = normalize_ocr_provider(ocr_provider)
    imported_count = 0
    skipped_count = 0
    errors: list[str] = []

    for paper in papers:
        pdf_url = paper.get("pdf_url")
        title = _truncate_title(paper.get("title") or "Untitled Paper")

        if not pdf_url:
            skipped_count += 1
            continue

        if title in existing_titles:
            skipped_count += 1
            continue

        try:
            document = _stream_pdf_to_document(pdf_url, title, folder)
            _apply_ocr_settings_to_document(document, skip_ocr, provider)
            existing_titles.add(title)
            imported_count += 1
        except Exception as exc:
            print(f"Issue saving Scholar Inbox PDF '{title}': {exc}")
            skipped_count += 1
            errors.append(f"{title}: {exc}")

    unmatched_count = len(unmatched_titles)
    parts = [f"Imported {imported_count} paper(s) from Scholar Inbox."]
    if skipped_count:
        parts.append(f"{skipped_count} skipped (duplicates or download errors).")
    if unmatched_count:
        parts.append(f"{unmatched_count} title(s) had no arXiv match.")

    return {
        "ok": True,
        "digest_found": True,
        "imported": imported_count,
        "skipped": skipped_count,
        "unmatched": unmatched_count,
        "titles_found": titles_found,
        "message": " ".join(parts),
        "should_stamp_daily": True,
        "unmatched_titles": unmatched_titles[:20],
        "errors": errors[:10],
    }


def run_scholar_auto_import() -> dict[str, Any]:
    """django-q worker entrypoint for startup auto-import."""
    from api.apps import _parse_last_import_date

    prefs = load_user_preferences()
    user_data = prefs.get("user_preferences", {})
    scholar_prefs = user_data.get("scholar_inbox", {})
    if not isinstance(scholar_prefs, dict):
        return {"ok": False, "message": "Scholar Inbox preferences missing."}

    if not scholar_prefs.get("auto_import", False):
        return {"ok": True, "message": "Auto-import disabled.", "skipped": True}

    last_import_date = _parse_last_import_date(scholar_prefs.get("last_import_date"))
    if last_import_date == date.today():
        return {"ok": True, "message": "Already imported today.", "skipped": True}

    amount_to_import = scholar_prefs.get("amount_to_import", 1)
    if amount_to_import == 0 or amount_to_import == "0":
        return {"ok": True, "message": "Auto-import amount is 0.", "skipped": True}

    print(f"Scholar Inbox auto-import starting (amount={amount_to_import})...")
    try:
        result = import_scholar_inbox_papers(amount_to_import)
    except ScholarInboxError as exc:
        print(f"Scholar Inbox auto-import failed: {exc.message}")
        return {
            "ok": False,
            "message": exc.message,
            "code": exc.code,
            "should_stamp_daily": False,
        }
    except Exception as exc:
        print(f"Scholar Inbox auto-import crashed: {exc}")
        return {
            "ok": False,
            "message": str(exc),
            "should_stamp_daily": False,
        }

    if result.get("should_stamp_daily"):
        _stamp_last_import_date()
        print(f"Scholar Inbox auto-import finished: {result.get('message')}")
    else:
        print(
            "Scholar Inbox auto-import did not stamp today "
            f"(will retry on next startup): {result.get('message')}"
        )

    return result


_queued_auto_import_this_process = False


def queue_scholar_auto_import() -> str | None:
    """Enqueue auto-import on django-q if enabled and not already done today."""
    global _queued_auto_import_this_process
    if _queued_auto_import_this_process:
        return None
    _queued_auto_import_this_process = True

    prefs = load_user_preferences()
    user_data = prefs.get("user_preferences", {})
    scholar_prefs = user_data.get("scholar_inbox", {})
    if not isinstance(scholar_prefs, dict) or not scholar_prefs.get("auto_import", False):
        return None

    from api.apps import _parse_last_import_date

    if _parse_last_import_date(scholar_prefs.get("last_import_date")) == date.today():
        return None

    amount_to_import = scholar_prefs.get("amount_to_import", 1)
    if amount_to_import == 0 or amount_to_import == "0":
        return None

    return async_task(
        "api.scholar_inbox_import.run_scholar_auto_import",
        timeout=1800,
    )
