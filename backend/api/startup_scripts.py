"""Validate and run user-configured startup shell scripts in a background worker."""

from __future__ import annotations

import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .utils import get_app_data_dir

SHELL_SCRIPT_SUFFIXES = {".sh", ".bash", ".zsh"}
MAX_SCRIPTS = 50
SCRIPT_TIMEOUT_SECONDS = 600
MAX_OUTPUT_CHARS = 2000

_STATUS_FILENAME = "startup_scripts_status.json"
_queued_this_process = False


def _status_path() -> Path:
    return Path(get_app_data_dir()) / _STATUS_FILENAME


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_status() -> dict:
    path = _status_path()
    if not path.is_file():
        return {
            "run_id": None,
            "status": "idle",
            "started_at": None,
            "finished_at": None,
            "results": [],
            "summary": None,
        }
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {
        "run_id": None,
        "status": "idle",
        "started_at": None,
        "finished_at": None,
        "results": [],
        "summary": None,
    }


def write_status(payload: dict) -> None:
    path = _status_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def get_startup_scripts_status() -> dict:
    return _read_status()


def _truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _has_shell_shebang(path: Path) -> bool:
    try:
        with open(path, "rb") as handle:
            first_line = handle.readline(256)
    except OSError:
        return False
    if not first_line.startswith(b"#!"):
        return False
    lowered = first_line.lower()
    return any(token in lowered for token in (b"/sh", b"bash", b"zsh", b"dash"))


def validate_shell_script_path(path_str: str) -> tuple[bool, str, str | None]:
    """
    Validate a user-provided shell script path.

    Returns (ok, error_message, normalized_absolute_path).
    """
    if path_str is None:
        return False, "Path is empty.", None

    raw = str(path_str).strip()
    if not raw:
        return False, "Path is empty.", None

    if "\x00" in raw:
        return False, "Path contains invalid characters.", None

    path = Path(raw).expanduser()
    if not path.is_absolute():
        return False, "Use an absolute path (for example /home/you/scripts/setup.sh).", None

    try:
        resolved = path.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        return False, f"Invalid path: {exc}", None

    if not resolved.is_absolute():
        return False, "Use an absolute path (for example /home/you/scripts/setup.sh).", None

    if not resolved.exists():
        return False, f"File does not exist: {resolved}", None

    if not resolved.is_file():
        return False, f"Path is not a file: {resolved}", None

    if resolved.is_symlink():
        try:
            if not resolved.resolve(strict=True).is_file():
                return False, f"Symlink does not point to a file: {resolved}", None
        except OSError as exc:
            return False, f"Could not resolve symlink: {exc}", None

    suffix_ok = resolved.suffix.lower() in SHELL_SCRIPT_SUFFIXES
    shebang_ok = _has_shell_shebang(resolved)
    if not suffix_ok and not shebang_ok:
        return (
            False,
            "Not a shell script. Use a .sh/.bash/.zsh file or a script with a shell shebang (#!/bin/bash).",
            None,
        )

    return True, "", str(resolved)


def sanitize_startup_script_paths(paths) -> tuple[list[str], list[dict]]:
    """Normalize and validate a list of script paths. Drops blanks; reports errors."""
    if paths is None:
        return [], []
    if isinstance(paths, str):
        paths = [paths]
    if not isinstance(paths, (list, tuple)):
        return [], [{"path": "", "error": "startup_scripts must be a list of absolute paths."}]

    cleaned: list[str] = []
    errors: list[dict] = []
    seen: set[str] = set()

    for item in paths:
        if item is None:
            continue
        raw = str(item).strip()
        if not raw:
            continue
        if len(cleaned) >= MAX_SCRIPTS:
            errors.append(
                {
                    "path": raw,
                    "error": f"Too many scripts (maximum {MAX_SCRIPTS}).",
                }
            )
            continue

        ok, message, normalized = validate_shell_script_path(raw)
        if not ok or not normalized:
            errors.append({"path": raw, "error": message})
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)

    return cleaned, errors


def load_configured_startup_scripts() -> list[str]:
    from .user_preferences import deep_get, load_user_preferences

    prefs = load_user_preferences()
    general = deep_get(prefs, "general", {}) or {}
    if not isinstance(general, dict):
        return []
    paths = general.get("startup_scripts", [])
    cleaned, _errors = sanitize_startup_script_paths(paths)
    return cleaned


def run_startup_scripts(script_paths: list[str] | None = None) -> dict:
    """Run configured startup scripts sequentially. Intended for django-q workers."""
    paths = script_paths if script_paths is not None else load_configured_startup_scripts()
    run_id = str(uuid.uuid4())
    started_at = _utc_now_iso()

    if not paths:
        payload = {
            "run_id": run_id,
            "status": "completed",
            "started_at": started_at,
            "finished_at": _utc_now_iso(),
            "results": [],
            "summary": None,
        }
        write_status(payload)
        return payload

    write_status(
        {
            "run_id": run_id,
            "status": "running",
            "started_at": started_at,
            "finished_at": None,
            "results": [],
            "summary": None,
        }
    )

    results: list[dict] = []
    for raw_path in paths:
        ok, message, normalized = validate_shell_script_path(raw_path)
        if not ok or not normalized:
            results.append(
                {
                    "path": str(raw_path),
                    "ok": False,
                    "exit_code": None,
                    "message": message,
                }
            )
            continue

        try:
            completed = subprocess.run(
                ["/bin/bash", normalized],
                capture_output=True,
                text=True,
                timeout=SCRIPT_TIMEOUT_SECONDS,
                check=False,
                env=os.environ.copy(),
            )
            stdout = _truncate(completed.stdout)
            stderr = _truncate(completed.stderr)
            if completed.returncode == 0:
                detail = stdout or "Completed successfully."
                results.append(
                    {
                        "path": normalized,
                        "ok": True,
                        "exit_code": 0,
                        "message": detail,
                    }
                )
            else:
                detail = stderr or stdout or f"Exited with code {completed.returncode}."
                results.append(
                    {
                        "path": normalized,
                        "ok": False,
                        "exit_code": completed.returncode,
                        "message": detail,
                    }
                )
        except subprocess.TimeoutExpired:
            results.append(
                {
                    "path": normalized,
                    "ok": False,
                    "exit_code": None,
                    "message": f"Timed out after {SCRIPT_TIMEOUT_SECONDS} seconds.",
                }
            )
        except OSError as exc:
            results.append(
                {
                    "path": normalized,
                    "ok": False,
                    "exit_code": None,
                    "message": f"Could not run script: {exc}",
                }
            )

    failures = [item for item in results if not item.get("ok")]
    if failures:
        status = "failed"
        if len(failures) == len(results):
            summary = f"All {len(results)} startup script(s) failed."
        else:
            summary = f"{len(failures)} of {len(results)} startup script(s) failed."
    else:
        status = "completed"
        summary = f"All {len(results)} startup script(s) completed successfully."

    payload = {
        "run_id": run_id,
        "status": status,
        "started_at": started_at,
        "finished_at": _utc_now_iso(),
        "results": results,
        "summary": summary,
    }
    write_status(payload)
    return payload


def queue_startup_scripts() -> str | None:
    """Enqueue startup scripts on the django-q worker. Returns task id or None."""
    global _queued_this_process
    if _queued_this_process:
        return None
    _queued_this_process = True

    paths = load_configured_startup_scripts()
    if not paths:
        write_status(
            {
                "run_id": None,
                "status": "idle",
                "started_at": None,
                "finished_at": None,
                "results": [],
                "summary": None,
            }
        )
        return None

    write_status(
        {
            "run_id": None,
            "status": "queued",
            "started_at": _utc_now_iso(),
            "finished_at": None,
            "results": [],
            "summary": "Startup scripts queued.",
        }
    )

    from api.task_queue import enqueue_task

    return enqueue_task(
        "api.startup_scripts.run_startup_scripts",
        paths,
        timeout=SCRIPT_TIMEOUT_SECONDS + 60,
    )
