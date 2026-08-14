import multiprocessing
import os
import socket
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Claude Desktop launches `api mcp` as a thin stdio bridge. Bail out before Django
# ASGI bootstrap so the MCP process stays light and does not need a live DB.
if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "mcp":
    from api.mcp.server import main as run_mcp

    run_mcp()
    raise SystemExit(0)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

import django
from django.core.asgi import get_asgi_application
from django.core.management import call_command

django.setup()

# Packaged worker entry: must run in its own process so signal handlers work.
if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "qcluster":
    from api.task_queue import run_qcluster_until_idle

    run_qcluster_until_idle()
    raise SystemExit(0)

application = get_asgi_application()


def _reserve_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def _write_mcp_discovery(port: int) -> None:
    try:
        from api.mcp.discovery import write_discovery

        path = write_discovery(port=port, host="127.0.0.1")
        print(f"MCP discovery written to {path}", flush=True)
    except Exception as exc:
        print(f"Could not write MCP discovery file: {exc}", flush=True)


def _ensure_mcp_launcher() -> None:
    try:
        from api.mcp.discovery import ensure_stable_mcp_launcher

        path = ensure_stable_mcp_launcher()
        if path is not None:
            print(f"MCP launcher written to {path}", flush=True)
    except Exception as exc:
        print(f"Could not write MCP launcher: {exc}", flush=True)


def _wait_for_port(host: str, port: int, timeout_seconds: float = 60.0) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.25):
                return True
        except OSError:
            time.sleep(0.05)
    return False


def _queue_deferred_startup_work() -> None:
    """
    Run after the API is accepting connections.

    Queue optional startup work after the first UI requests can be served. The
    enqueue helper starts a worker only when one of these features is enabled.
    """
    # Brief pause so the first UI fetches can land before heavy workers.
    time.sleep(0.75)
    try:
        from api.startup_scripts import queue_startup_scripts

        task_id = queue_startup_scripts()
        if task_id:
            print(
                f"Startup scripts queued on background worker (task {task_id}).",
                flush=True,
            )
    except Exception as exc:
        print(f"Could not queue startup scripts: {exc}", flush=True)

    try:
        from api.scholar_inbox_import import queue_scholar_auto_import

        task_id = queue_scholar_auto_import()
        if task_id:
            print(
                f"Scholar Inbox auto-import queued on background worker (task {task_id}).",
                flush=True,
            )
    except Exception as exc:
        print(f"Could not queue Scholar Inbox auto-import: {exc}", flush=True)


def _announce_when_listening(port: int) -> None:
    """
    Electron only trusts a bare `http://127.0.0.1:PORT` line (not uvicorn's log).
    Emit it once the port actually accepts connections, then start workers.
    """
    if _wait_for_port("127.0.0.1", port):
        print(f"http://127.0.0.1:{port}", flush=True)
        _queue_deferred_startup_work()
        return

    print(f"Timed out waiting for API to bind on 127.0.0.1:{port}", flush=True)
    print(f"http://127.0.0.1:{port}", flush=True)
    _queue_deferred_startup_work()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    _ensure_mcp_launcher()

    print("Checking for database migrations...", flush=True)
    try:
        call_command("migrate", interactive=False)
        print("Migrations applied successfully.", flush=True)
    except Exception as e:
        print(f"Error applying migrations: {e}", flush=True)

    port = _reserve_port()
    _write_mcp_discovery(port)

    threading.Thread(
        target=_announce_when_listening,
        args=(port,),
        daemon=True,
        name="announce-api-ready",
    ).start()

    import uvicorn

    # Keep uvicorn on the main thread (required for clean lifecycle / signals).
    uvicorn.run(application, host="127.0.0.1", port=port)
