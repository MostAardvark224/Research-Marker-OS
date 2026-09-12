"""Import standalone notes from uploaded or local Markdown files."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable

from django.db import transaction

from api import models


MARKDOWN_SUFFIX = ".md"
MAX_MARKDOWN_FILE_BYTES = 10 * 1024 * 1024
MAX_MARKDOWN_IMPORT_FILES = 1000
MAX_MARKDOWN_IMPORT_BYTES = 100 * 1024 * 1024


class NoteImportError(ValueError):
    """A user-correctable Markdown import error."""


def _raise_walk_error(error: OSError) -> None:
    raise error


def request_list(data, key: str) -> list[str]:
    """Read a list from either JSON data or a multipart QueryDict."""
    if hasattr(data, "getlist"):
        values = data.getlist(key)
    else:
        value = data.get(key, [])
        values = value if isinstance(value, list) else [value]

    if len(values) == 1 and isinstance(values[0], str):
        candidate = values[0].strip()
        if candidate.startswith("["):
            try:
                decoded = json.loads(candidate)
            except json.JSONDecodeError:
                decoded = None
            if isinstance(decoded, list):
                values = decoded

    return [str(value).strip() for value in values if str(value).strip()]


def _validated_absolute_path(raw_path: str, expected: str) -> Path:
    if "\x00" in raw_path:
        raise NoteImportError(f"Invalid path: {raw_path!r}.")

    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        raise NoteImportError(f"Path must be absolute: {raw_path}")

    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise NoteImportError(f"Could not access path {raw_path}: {exc}") from exc

    if expected == "file" and not resolved.is_file():
        raise NoteImportError(f"Path is not a file: {resolved}")
    if expected == "directory" and not resolved.is_dir():
        raise NoteImportError(f"Path is not a directory: {resolved}")
    return resolved


def collect_markdown_paths(
    file_paths: Iterable[str], directory_paths: Iterable[str]
) -> list[Path]:
    """Validate explicit paths and recursively collect Markdown files."""
    collected: list[Path] = []
    seen: set[Path] = set()

    def add_file(path: Path) -> None:
        if path.suffix.lower() != MARKDOWN_SUFFIX:
            raise NoteImportError(f"Only .md files can be imported: {path}")
        if path not in seen:
            seen.add(path)
            collected.append(path)
        if len(collected) > MAX_MARKDOWN_IMPORT_FILES:
            raise NoteImportError(
                f"An import can contain at most {MAX_MARKDOWN_IMPORT_FILES} Markdown files."
            )

    for raw_path in file_paths:
        add_file(_validated_absolute_path(raw_path, "file"))

    for raw_path in directory_paths:
        directory = _validated_absolute_path(raw_path, "directory")
        try:
            for current_root, directory_names, filenames in os.walk(
                directory,
                followlinks=False,
                onerror=_raise_walk_error,
            ):
                directory_names.sort(key=str.lower)
                for filename in sorted(filenames, key=str.lower):
                    if Path(filename).suffix.lower() != MARKDOWN_SUFFIX:
                        continue
                    path = (Path(current_root) / filename).resolve(strict=True)
                    if path.is_file():
                        add_file(path)
        except (OSError, RuntimeError) as exc:
            raise NoteImportError(f"Could not scan directory {directory}: {exc}") from exc

    return collected


def _decode_markdown(raw: bytes, label: str) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise NoteImportError(f"Markdown file is not valid UTF-8: {label}") from exc


def _title_from_filename(filename: str) -> str:
    return (Path(filename).stem.strip() or "Untitled note")[:255]


def prepare_note_imports(uploaded_files, file_paths, directory_paths) -> list[dict[str, str]]:
    """Validate and read every source before any notes are written."""
    prepared: list[dict[str, str]] = []
    total_bytes = 0

    for upload in uploaded_files:
        if len(prepared) >= MAX_MARKDOWN_IMPORT_FILES:
            raise NoteImportError(
                f"An import can contain at most {MAX_MARKDOWN_IMPORT_FILES} Markdown files."
            )
        filename = Path(upload.name).name
        if Path(filename).suffix.lower() != MARKDOWN_SUFFIX:
            raise NoteImportError(f"Only .md files can be imported: {filename}")
        size = getattr(upload, "size", 0)
        if size > MAX_MARKDOWN_FILE_BYTES:
            raise NoteImportError(f"Markdown file is larger than 10 MB: {filename}")
        if total_bytes + size > MAX_MARKDOWN_IMPORT_BYTES:
            raise NoteImportError("An import can contain at most 100 MB of Markdown content.")
        try:
            raw = upload.read()
        except OSError as exc:
            raise NoteImportError(f"Could not read uploaded file {filename}: {exc}") from exc
        total_bytes += len(raw)
        if total_bytes > MAX_MARKDOWN_IMPORT_BYTES:
            raise NoteImportError("An import can contain at most 100 MB of Markdown content.")
        prepared.append(
            {
                "title": _title_from_filename(filename),
                "content": _decode_markdown(raw, filename),
            }
        )

    for path in collect_markdown_paths(file_paths, directory_paths):
        if len(prepared) >= MAX_MARKDOWN_IMPORT_FILES:
            raise NoteImportError(
                f"An import can contain at most {MAX_MARKDOWN_IMPORT_FILES} Markdown files."
            )
        try:
            size = path.stat().st_size
            if size > MAX_MARKDOWN_FILE_BYTES:
                raise NoteImportError(f"Markdown file is larger than 10 MB: {path}")
            if total_bytes + size > MAX_MARKDOWN_IMPORT_BYTES:
                raise NoteImportError("An import can contain at most 100 MB of Markdown content.")
            raw = path.read_bytes()
        except NoteImportError:
            raise
        except OSError as exc:
            raise NoteImportError(f"Could not read Markdown file {path}: {exc}") from exc
        total_bytes += len(raw)
        if total_bytes > MAX_MARKDOWN_IMPORT_BYTES:
            raise NoteImportError("An import can contain at most 100 MB of Markdown content.")
        prepared.append(
            {
                "title": _title_from_filename(path.name),
                "content": _decode_markdown(raw, str(path)),
            }
        )

    if not prepared:
        raise NoteImportError("Choose at least one Markdown file, file path, or directory path.")
    return prepared


@transaction.atomic
def create_imported_notes(prepared, folder, starting_sort_order: int):
    notes = []
    for offset, item in enumerate(prepared):
        notes.append(
            models.StandaloneNote.objects.create(
                title=item["title"],
                content=item["content"],
                folder=folder,
                sort_order=starting_sort_order + offset,
            )
        )
    return notes
