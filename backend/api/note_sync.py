"""Conflict-safe, one-way Markdown note imports for PDF notepads."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from django.db import transaction
from django.utils import timezone

from .models import Annotations, Document, NoteSyncBinding, NoteSyncRevision
from .user_preferences import deep_get, load_user_preferences

MAX_NOTE_DIRECTORIES = 20
MAX_MARKDOWN_FILES = 5000
MAX_MARKDOWN_BYTES = 10 * 1024 * 1024
NOTE_MARKER_RE = re.compile(r"(?im)^[ \t]*#rm:([a-z0-9_-]{8,64})[ \t]*$")


def note_marker(code: str) -> str:
    return f"#rm:{code}"


def _hash_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def sanitize_note_sync_directories(directories) -> tuple[list[str], list[dict]]:
    if directories is None:
        return [], []
    if isinstance(directories, str):
        directories = [directories]
    if not isinstance(directories, (list, tuple)):
        return [], [{"path": "", "error": "note_sync_directories must be a list."}]

    cleaned: list[str] = []
    errors: list[dict] = []
    seen: set[str] = set()
    for item in directories:
        raw = str(item or "").strip()
        if not raw:
            continue
        if len(cleaned) >= MAX_NOTE_DIRECTORIES:
            errors.append(
                {"path": raw, "error": f"Too many directories (maximum {MAX_NOTE_DIRECTORIES})."}
            )
            continue
        path = Path(raw).expanduser()
        if not path.is_absolute():
            errors.append({"path": raw, "error": "Use an absolute directory path."})
            continue
        try:
            resolved = path.resolve(strict=True)
        except OSError as exc:
            errors.append({"path": raw, "error": f"Directory is unavailable: {exc}"})
            continue
        if not resolved.is_dir():
            errors.append({"path": raw, "error": "Path is not a directory."})
            continue
        normalized = str(resolved)
        if normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)
    return cleaned, errors


def load_note_sync_directories() -> tuple[list[str], list[dict]]:
    preferences = load_user_preferences()
    general = deep_get(preferences, "general", {}) or {}
    if not isinstance(general, dict):
        return [], []
    return sanitize_note_sync_directories(general.get("note_sync_directories", []))


def _read_stable_markdown(path: Path) -> str:
    before = path.stat()
    if before.st_size > MAX_MARKDOWN_BYTES:
        raise ValueError("Markdown file is larger than 10 MB.")
    content = path.read_text(encoding="utf-8")
    after = path.stat()
    if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
        raise ValueError("File changed while it was being read; save it and refresh again.")
    return content


def _content_without_marker(content: str, code: str) -> str:
    target = code.upper()
    kept = []
    for line in content.splitlines(keepends=True):
        match = NOTE_MARKER_RE.fullmatch(line.rstrip("\r\n"))
        if match and match.group(1).upper() == target:
            continue
        kept.append(line)
    return "".join(kept)


def scan_markdown_notes() -> dict:
    directories, directory_errors = load_note_sync_directories()
    files_by_code: dict[str, list[dict]] = {}
    code_errors: dict[str, list[str]] = {}
    scan_errors = [
        {"status": "error", "file_path": error["path"], "message": error["error"]}
        for error in directory_errors
    ]
    seen_paths: set[str] = set()
    file_count = 0

    for raw_root in directories:
        root = Path(raw_root)
        try:
            candidates = root.rglob("*")
            for candidate in candidates:
                if file_count >= MAX_MARKDOWN_FILES:
                    scan_errors.append(
                        {
                            "status": "error",
                            "file_path": raw_root,
                            "message": f"Stopped after {MAX_MARKDOWN_FILES} Markdown files.",
                        }
                    )
                    break
                if candidate.suffix.lower() != ".md" or not candidate.is_file():
                    continue
                try:
                    resolved = candidate.resolve(strict=True)
                    if not resolved.is_relative_to(root):
                        continue
                    normalized = str(resolved)
                    if normalized in seen_paths:
                        continue
                    seen_paths.add(normalized)
                    file_count += 1
                    raw_content = _read_stable_markdown(resolved)
                    codes = {
                        match.upper() for match in NOTE_MARKER_RE.findall(raw_content)
                    }
                    if not codes:
                        continue
                    if len(codes) > 1:
                        message = "File contains more than one Research Marker code."
                        for code in codes:
                            code_errors.setdefault(code, []).append(message)
                        continue
                    code = next(iter(codes))
                    files_by_code.setdefault(code, []).append(
                        {
                            "path": normalized,
                            "raw_content": raw_content,
                            "content": _content_without_marker(raw_content, code),
                            "file_hash": _hash_text(raw_content),
                        }
                    )
                except (OSError, UnicodeError, ValueError) as exc:
                    scan_errors.append(
                        {
                            "status": "error",
                            "file_path": str(candidate),
                            "message": str(exc),
                        }
                    )
        except OSError as exc:
            scan_errors.append(
                {"status": "error", "file_path": raw_root, "message": str(exc)}
            )

    return {
        "directories": directories,
        "files_by_code": files_by_code,
        "code_errors": code_errors,
        "scan_errors": scan_errors,
    }


def _base_result(document: Document, status: str, message: str, **extra) -> dict:
    result = {
        "document_id": document.id,
        "title": document.title,
        "code": document.note_sync_code,
        "marker": note_marker(document.note_sync_code),
        "status": status,
        "message": message,
    }
    result.update(extra)
    return result


def _save_binding_baseline(
    binding: NoteSyncBinding,
    *,
    file_path: str,
    file_hash: str,
    app_content: str,
) -> None:
    binding.file_path = file_path
    binding.last_file_hash = file_hash
    binding.last_app_hash = _hash_text(app_content)
    binding.last_synced_at = timezone.now()
    binding.save()


def _replace_notepad(
    document: Document,
    annotation: Annotations,
    binding: NoteSyncBinding,
    file_entry: dict,
    *,
    content: str,
    reason: str,
) -> None:
    NoteSyncRevision.objects.create(
        document=document,
        content=annotation.notepad or "",
        reason=reason,
        source_file_path=file_entry["path"],
    )
    annotation.notepad = content
    annotation.save(update_fields=["notepad", "updated_at"])
    _save_binding_baseline(
        binding,
        file_path=file_entry["path"],
        file_hash=file_entry["file_hash"],
        app_content=content,
    )


def refresh_document_note(document: Document, scan: dict | None = None) -> dict:
    scan = scan or scan_markdown_notes()
    code = document.note_sync_code.upper()
    if scan["code_errors"].get(code):
        return _base_result(
            document,
            "conflict",
            scan["code_errors"][code][0],
            conflict_type="invalid_marker",
        )

    matches = scan["files_by_code"].get(code, [])
    if len(matches) > 1:
        return _base_result(
            document,
            "conflict",
            "More than one Markdown file contains this paper code.",
            conflict_type="duplicate_code",
            file_paths=[entry["path"] for entry in matches],
        )
    if not matches:
        return _base_result(
            document,
            "unmatched",
            "No Markdown file with this paper code was found.",
        )

    file_entry = matches[0]
    with transaction.atomic():
        annotation, _ = Annotations.objects.select_for_update().get_or_create(
            document=document,
            defaults={"highlight_data": [], "notepad": "", "sticky_note_data": []},
        )
        binding, created = NoteSyncBinding.objects.select_for_update().get_or_create(
            document=document,
            defaults={"file_path": file_entry["path"]},
        )
        app_content = annotation.notepad or ""
        app_hash = _hash_text(app_content)
        file_hash = file_entry["file_hash"]

        if created or not binding.last_file_hash or not binding.last_app_hash:
            if not app_content or app_content == file_entry["content"]:
                if app_content != file_entry["content"]:
                    _replace_notepad(
                        document,
                        annotation,
                        binding,
                        file_entry,
                        content=file_entry["content"],
                        reason="initial_import",
                    )
                    return _base_result(
                        document,
                        "imported",
                        "Imported Markdown notes.",
                        file_path=file_entry["path"],
                        last_synced_at=binding.last_synced_at,
                        notepad=file_entry["content"],
                    )
                _save_binding_baseline(
                    binding,
                    file_path=file_entry["path"],
                    file_hash=file_hash,
                    app_content=app_content,
                )
                return _base_result(
                    document,
                    "linked",
                    "Linked matching Markdown notes.",
                    file_path=file_entry["path"],
                    last_synced_at=binding.last_synced_at,
                )

            binding.file_path = file_entry["path"]
            binding.save(update_fields=["file_path", "updated_at"])
            return _base_result(
                document,
                "conflict",
                "Both the notepad and Markdown file already contain different notes.",
                conflict_type="initial_mismatch",
                file_path=file_entry["path"],
            )

        file_changed = file_hash != binding.last_file_hash
        app_changed = app_hash != binding.last_app_hash
        binding.file_path = file_entry["path"]
        binding.save(update_fields=["file_path", "updated_at"])

        if file_changed and app_changed:
            return _base_result(
                document,
                "conflict",
                "The Markdown file and Research Marker notepad both changed.",
                conflict_type="both_changed",
                file_path=file_entry["path"],
                last_synced_at=binding.last_synced_at,
            )
        if file_changed:
            _replace_notepad(
                document,
                annotation,
                binding,
                file_entry,
                content=file_entry["content"],
                reason="external_update",
            )
            return _base_result(
                document,
                "imported",
                "Imported updated Markdown notes.",
                file_path=file_entry["path"],
                last_synced_at=binding.last_synced_at,
                notepad=file_entry["content"],
            )
        if app_changed:
            return _base_result(
                document,
                "app_changed",
                "Research Marker notes changed; the Markdown file was left untouched.",
                file_path=file_entry["path"],
                last_synced_at=binding.last_synced_at,
            )
        return _base_result(
            document,
            "unchanged",
            "Notes are already up to date.",
            file_path=file_entry["path"],
            last_synced_at=binding.last_synced_at,
        )


def refresh_all_notes() -> dict:
    scan = scan_markdown_notes()
    results: list[dict] = list(scan["scan_errors"])
    matched_codes = set(scan["files_by_code"]) | set(scan["code_errors"])
    documents = {
        document.note_sync_code.upper(): document
        for document in Document.objects.only("id", "title", "note_sync_code")
        if document.note_sync_code.upper() in matched_codes
    }
    for code in sorted(matched_codes):
        document = documents.get(code)
        if document is None:
            for message in scan["code_errors"].get(code, []):
                results.append(
                    {
                        "status": "error",
                        "code": code,
                        "message": message,
                    }
                )
            for entry in scan["files_by_code"].get(code, []):
                results.append(
                    {
                        "status": "unknown_code",
                        "code": code,
                        "file_path": entry["path"],
                        "message": "No paper uses this Research Marker code.",
                    }
                )
            continue
        result = refresh_document_note(document, scan)
        result.pop("notepad", None)
        results.append(result)

    for binding in NoteSyncBinding.objects.select_related("document"):
        if binding.document.note_sync_code.upper() not in matched_codes:
            results.append(
                _base_result(
                    binding.document,
                    "unmatched",
                    "The previously linked Markdown file was not found.",
                    file_path=binding.file_path,
                    last_synced_at=binding.last_synced_at,
                )
            )

    counts: dict[str, int] = {}
    for result in results:
        status = result.get("status", "error")
        counts[status] = counts.get(status, 0) + 1
    return {"directories": scan["directories"], "counts": counts, "results": results}


def get_document_sync_state(document: Document) -> dict:
    binding = NoteSyncBinding.objects.filter(document=document).first()
    return _base_result(
        document,
        "linked" if binding else "unlinked",
        "Markdown file linked." if binding else "Paste this code into a Markdown file.",
        file_path=binding.file_path if binding else "",
        last_synced_at=binding.last_synced_at if binding else None,
    )


def resolve_document_conflict(document: Document, action: str) -> dict:
    if action not in {"keep_both", "use_markdown", "keep_research_marker"}:
        raise ValueError("Unknown conflict resolution action.")
    scan = scan_markdown_notes()
    matches = scan["files_by_code"].get(document.note_sync_code.upper(), [])
    if len(matches) != 1:
        raise ValueError("The paper must match exactly one Markdown file before resolving.")
    file_entry = matches[0]

    with transaction.atomic():
        annotation, _ = Annotations.objects.select_for_update().get_or_create(
            document=document,
            defaults={"highlight_data": [], "notepad": "", "sticky_note_data": []},
        )
        binding, _ = NoteSyncBinding.objects.select_for_update().get_or_create(
            document=document,
            defaults={"file_path": file_entry["path"]},
        )
        app_content = annotation.notepad or ""
        if action == "keep_research_marker":
            _save_binding_baseline(
                binding,
                file_path=file_entry["path"],
                file_hash=file_entry["file_hash"],
                app_content=app_content,
            )
            return _base_result(
                document,
                "kept_app",
                "Kept the Research Marker notes. The Markdown file was not changed.",
                file_path=file_entry["path"],
                last_synced_at=binding.last_synced_at,
                notepad=app_content,
            )

        if action == "keep_both":
            external = file_entry["content"]
            if not app_content:
                merged = external
            elif not external:
                merged = app_content
            else:
                merged = f"{app_content.rstrip()}\n\n---\n\n{external.lstrip()}"
            reason = "conflict_keep_both"
            message = "Combined both versions in the Research Marker notepad."
            status = "kept_both"
        else:
            merged = file_entry["content"]
            reason = "conflict_use_markdown"
            message = "Used the Markdown version. The previous notepad was saved as a revision."
            status = "imported"

        _replace_notepad(
            document,
            annotation,
            binding,
            file_entry,
            content=merged,
            reason=reason,
        )
        return _base_result(
            document,
            status,
            message,
            file_path=file_entry["path"],
            last_synced_at=binding.last_synced_at,
            notepad=merged,
        )
