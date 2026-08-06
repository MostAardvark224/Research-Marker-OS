import os
import sys
import socket
import threading
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


def _reserve_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def _write_mcp_discovery(port: int) -> None:
    try:
        from api.mcp.discovery import write_discovery

        path = write_discovery(port=port, host="127.0.0.1")
        print(f"MCP discovery written to {path}")
    except Exception as exc:
        print(f"Could not write MCP discovery file: {exc}")


def _ensure_mcp_launcher() -> None:
    try:
        from api.mcp.discovery import ensure_stable_mcp_launcher

        path = ensure_stable_mcp_launcher()
        if path is not None:
            print(f"MCP launcher written to {path}")
    except Exception as exc:
        print(f"Could not write MCP launcher: {exc}")


if __name__ == "__main__":
    _ensure_mcp_launcher()

    print("Checking for database migrations...")
    try:
        call_command("migrate", interactive=False)
        print("Migrations applied successfully.")
    except Exception as e:
        print(f"Error applying migrations: {e}")

    def run_qcluster():
        try:
            print("Starting background task worker (qcluster)...")
            call_command("qcluster")
        except Exception as e:
            print(f"Q Cluster Error: {e}")

    q_thread = threading.Thread(target=run_qcluster, daemon=True)
    q_thread.start()

    port = _reserve_port()
    _write_mcp_discovery(port)
    # Electron and MCP clients parse this exact URL shape.
    print(f"http://127.0.0.1:{port}")
    import uvicorn

    uvicorn.run(application, host="127.0.0.1", port=port)
