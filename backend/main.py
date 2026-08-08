import atexit
import multiprocessing
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

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
application = get_asgi_application()

# Packaged worker entry: must run in its own process so signal handlers work.
if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "qcluster":
    call_command("qcluster")
    raise SystemExit(0)


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

    Startup scripts / Scholar Inbox auto-import share SQLite with the UI's first
    fetches. Give the first env-vars / complete-fetch calls a brief head start.
    """
    time.sleep(1.5)
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
    Emit it once the port actually accepts connections.
    """
    if _wait_for_port("127.0.0.1", port):
        print(f"http://127.0.0.1:{port}", flush=True)
        _queue_deferred_startup_work()
        return

    print(f"Timed out waiting for API to bind on 127.0.0.1:{port}", flush=True)
    print(f"http://127.0.0.1:{port}", flush=True)


def _start_qcluster_process() -> subprocess.Popen:
    """
    django-q registers POSIX signal handlers, which only work in a process main
    thread. Spawning a sibling process avoids the threaded `call_command` failure.
    """
    print("Starting background task worker (qcluster)...", flush=True)
    if getattr(sys, "frozen", False):
        cmd = [sys.executable, "qcluster"]
    else:
        cmd = [sys.executable, str(Path(__file__).resolve()), "qcluster"]

    return subprocess.Popen(
        cmd,
        env=os.environ.copy(),
        stdout=sys.stdout,
        stderr=sys.stderr,
    )


if __name__ == "__main__":
    multiprocessing.freeze_support()
    _ensure_mcp_launcher()

    print("Checking for database migrations...", flush=True)
    try:
        call_command("migrate", interactive=False)
        print("Migrations applied successfully.", flush=True)
    except Exception as e:
        print(f"Error applying migrations: {e}", flush=True)

    qcluster_proc = None
    try:
        qcluster_proc = _start_qcluster_process()
    except Exception as exc:
        print(f"Q Cluster Error: {exc}", flush=True)

    def _stop_qcluster() -> None:
        if qcluster_proc is None or qcluster_proc.poll() is not None:
            return
        qcluster_proc.terminate()
        try:
            qcluster_proc.wait(timeout=5)
        except Exception:
            qcluster_proc.kill()

    atexit.register(_stop_qcluster)

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
    try:
        uvicorn.run(application, host="127.0.0.1", port=port)
    finally:
        _stop_qcluster()
