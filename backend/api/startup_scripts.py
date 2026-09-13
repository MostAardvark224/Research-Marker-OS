"""Validate and run user-configured startup shell scripts in a background worker."""

from __future__ import annotations

import json
import os
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .utils import get_app_data_dir

SHELL_SCRIPT_SUFFIXES = {".sh", ".bash", ".zsh"}
MAX_SCRIPTS = 50
SCRIPT_TIMEOUT_SECONDS = 600
MAX_OUTPUT_CHARS = 2000

_STATUS_FILENAME = "startup_scripts_status.json"
_RUNTIME_STATUS_FILENAME = "shell_scripts_status.json"
_queued_this_process = False
_runtime_queue_lock = threading.Lock()


class ShellScriptsBusyError(RuntimeError):
    pass


def _status_path() -> Path:
    return Path(get_app_data_dir()) / _STATUS_FILENAME


def _runtime_status_path() -> Path:
    return Path(get_app_data_dir()) / _RUNTIME_STATUS_FILENAME


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_status() -> dict:
    return {
        "run_id": None,
        "status": "idle",
        "started_at": None,
        "finished_at": None,
        "results": [],
        "summary": None,
    }


def _read_status(path: Path | None = None) -> dict:
    path = path or _status_path()
    if not path.is_file():
        return _empty_status()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return _empty_status()


def write_status(payload: dict, path: Path | None = None) -> None:
    path = path or _status_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with open(temporary_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass


def get_startup_scripts_status() -> dict:
    return _read_status()


def get_shell_scripts_status() -> dict:
    return _read_status(_runtime_status_path())


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


def sanitize_shell_script_entries(entries) -> tuple[list[dict], list[dict]]:
    """Validate stored script entries while accepting the legacy string format."""
    if entries is None:
        return [], []
    if isinstance(entries, (str, dict)):
        entries = [entries]
    if not isinstance(entries, (list, tuple)):
        return [], [{"path": "", "error": "shell_scripts must be a list."}]

    normalized_entries: list[dict] = []
    errors: list[dict] = []
    seen: set[str] = set()

    for item in entries:
        if isinstance(item, str):
            raw_path = item
            run_on_startup = True
        elif isinstance(item, dict):
            raw_path = item.get("path", "")
            run_on_startup = item.get("run_on_startup", False)
            if not isinstance(run_on_startup, bool):
                errors.append(
                    {
                        "path": str(raw_path or ""),
                        "error": "run_on_startup must be true or false.",
                    }
                )
                continue
        else:
            errors.append({"path": "", "error": "Each shell script must be a path or object."})
            continue

        raw_path = str(raw_path or "").strip()
        if not raw_path:
            continue
        if len(normalized_entries) >= MAX_SCRIPTS:
            errors.append(
                {"path": raw_path, "error": f"Too many scripts (maximum {MAX_SCRIPTS})."}
            )
            continue

        ok, message, normalized = validate_shell_script_path(raw_path)
        if not ok or not normalized:
            errors.append({"path": raw_path, "error": message})
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        normalized_entries.append(
            {"path": normalized, "run_on_startup": run_on_startup}
        )

    return normalized_entries, errors


def load_configured_shell_scripts() -> list[dict]:
    from .user_preferences import deep_get, load_user_preferences

    prefs = load_user_preferences()
    general = deep_get(prefs, "general", {}) or {}
    if not isinstance(general, dict):
        return []
    raw_entries = general.get("shell_scripts")
    if raw_entries is None:
        raw_entries = general.get("startup_scripts", [])
    cleaned, _errors = sanitize_shell_script_entries(raw_entries)
    return cleaned


def load_configured_startup_scripts() -> list[str]:
    return [
        entry["path"]
        for entry in load_configured_shell_scripts()
        if entry["run_on_startup"]
    ]


def run_shell_scripts(
    script_paths: list[str],
    run_id: str | None = None,
    run_kind: str = "runtime",
) -> dict:
    """Run validated shell scripts sequentially. Intended for django-q workers."""
    status_path = _status_path() if run_kind == "startup" else _runtime_status_path()
    run_id = run_id or str(uuid.uuid4())
    started_at = _utc_now_iso()

    if not script_paths:
        payload = {
            "run_id": run_id,
            "status": "completed",
            "started_at": started_at,
            "finished_at": _utc_now_iso(),
            "results": [],
            "summary": None,
        }
        write_status(payload, status_path)
        return payload

    write_status(
        {
            "run_id": run_id,
            "status": "running",
            "started_at": started_at,
            "finished_at": None,
            "results": [],
            "summary": None,
        },
        status_path,
    )

    results: list[dict] = []
    for raw_path in script_paths:
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
    script_label = "startup script" if run_kind == "startup" else "shell script"
    if failures:
        status = "failed"
        if len(failures) == len(results):
            summary = f"All {len(results)} {script_label}(s) failed."
        else:
            summary = f"{len(failures)} of {len(results)} {script_label}(s) failed."
    else:
        status = "completed"
        summary = f"All {len(results)} {script_label}(s) completed successfully."

    payload = {
        "run_id": run_id,
        "status": status,
        "started_at": started_at,
        "finished_at": _utc_now_iso(),
        "results": results,
        "summary": summary,
    }
    write_status(payload, status_path)
    return payload


def run_startup_scripts(script_paths: list[str] | None = None) -> dict:
    """Run configured startup scripts sequentially. Intended for django-q workers."""
    paths = script_paths if script_paths is not None else load_configured_startup_scripts()
    return run_shell_scripts(paths, run_kind="startup")


def queue_shell_scripts(script_paths: list[str]) -> dict:
    """Queue a runtime batch after confirming every path is currently configured."""
    configured = {entry["path"] for entry in load_configured_shell_scripts()}
    cleaned, errors = sanitize_startup_script_paths(script_paths)
    if errors:
        raise ValueError(errors[0]["error"])
    if not cleaned:
        raise ValueError("Select at least one configured shell script.")
    if any(path not in configured for path in cleaned):
        raise ValueError("Only shell scripts saved in Settings can be run.")

    with _runtime_queue_lock:
        current_status = get_shell_scripts_status()
        if current_status.get("status") in {"queued", "running"}:
            raise ShellScriptsBusyError("A shell script batch is already running.")

        run_id = str(uuid.uuid4())
        write_status(
            {
                "run_id": run_id,
                "status": "queued",
                "started_at": _utc_now_iso(),
                "finished_at": None,
                "results": [],
                "summary": f"Queued {len(cleaned)} shell script(s).",
            },
            _runtime_status_path(),
        )

    from api.task_queue import enqueue_task

    try:
        task_id = enqueue_task(
            "api.startup_scripts.run_shell_scripts",
            cleaned,
            run_id,
            "runtime",
            timeout=(SCRIPT_TIMEOUT_SECONDS * len(cleaned)) + 60,
        )
    except Exception as exc:
        write_status(
            {
                "run_id": run_id,
                "status": "failed",
                "started_at": _utc_now_iso(),
                "finished_at": _utc_now_iso(),
                "results": [],
                "summary": f"Could not queue shell scripts: {exc}",
            },
            _runtime_status_path(),
        )
        raise
    return {"run_id": run_id, "task_id": task_id, "status": "queued"}


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
        timeout=(SCRIPT_TIMEOUT_SECONDS * len(paths)) + 60,
    )
