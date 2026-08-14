import os
import sys
from datetime import date

from django.apps import AppConfig


_MANAGEMENT_COMMANDS_SKIP_STARTUP = {
    "migrate",
    "makemigrations",
    "qcluster",
    "test",
    "shell",
    "run_embs",
    "collectstatic",
    "mcp",
    "check",
    "showmigrations",
}


def _parse_last_import_date(value):
    if value is None or value == "" or value == "null":
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _should_run_startup_hooks() -> bool:
    # Skip the parent process during `manage.py runserver` autoreload only.
    if "runserver" in sys.argv and os.environ.get("RUN_MAIN") != "true":
        return False
    if any(cmd in sys.argv for cmd in _MANAGEMENT_COMMANDS_SKIP_STARTUP):
        return False
    return True


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        from api.paper_context import signals as _paper_context_signals  # noqa: F401

        # Background entrypoints are included explicitly by api.spec. Importing
        # them here would load OCR, PyMuPDF and the scientific stack in every
        # API, migration, monitor and worker process before they are needed.

        # Skip the parent process during `manage.py runserver` autoreload only.
        if "runserver" in sys.argv and os.environ.get("RUN_MAIN") != "true":
            return

        # Dev / honcho: publish MCP discovery for the runserver bind address.
        if "runserver" in sys.argv or os.environ.get("RESEARCH_MARKER_WRITE_MCP_DISCOVERY") == "1":
            try:
                from api.mcp.discovery import write_discovery

                port = (
                    os.environ.get("RESEARCH_MARKER_API_PORT")
                    or os.environ.get("PORT")
                    or "8000"
                )
                if "runserver" in sys.argv:
                    idx = sys.argv.index("runserver")
                    for arg in sys.argv[idx + 1 :]:
                        if arg.startswith("-"):
                            continue
                        if arg.startswith("127.0.0.1:") or arg.startswith("0.0.0.0:"):
                            port = arg.rsplit(":", 1)[-1]
                            break
                        if arg.isdigit() and 1 <= int(arg) <= 65535:
                            port = arg
                            break
                write_discovery(port=port, host="127.0.0.1")
                print(f"MCP discovery published for http://127.0.0.1:{port}/api")
            except Exception as exc:
                print(f"Could not write MCP discovery on startup: {exc}")

        if not _should_run_startup_hooks():
            return

        # Packaged `main.py` queues these after migrate + qcluster start.
        # Dev `runserver` (migrate already finished) can queue here.
        if "runserver" in sys.argv:
            self._queue_scholar_auto_import()
            self._queue_startup_scripts()

    def _queue_scholar_auto_import(self):
        try:
            from api.scholar_inbox_import import queue_scholar_auto_import

            task_id = queue_scholar_auto_import()
            if task_id:
                print(f"Scholar Inbox auto-import queued on background worker (task {task_id}).")
        except Exception as exc:
            print(f"Could not queue Scholar Inbox auto-import: {exc}")

    def _queue_startup_scripts(self):
        try:
            from api.startup_scripts import queue_startup_scripts

            task_id = queue_startup_scripts()
            if task_id:
                print(f"Startup scripts queued on background worker (task {task_id}).")
        except Exception as exc:
            print(f"Could not queue startup scripts: {exc}")
