import os
import sys
import socket
import threading
import uvicorn
from pathlib import Path
from django.core.management import call_command

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

import django
from django.core.asgi import get_asgi_application

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


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "mcp":
        from api.mcp.server import main as run_mcp

        run_mcp()
        raise SystemExit(0)

    django.setup()

    print("Checking for database migrations...")
    try:
        call_command('migrate', interactive=False)
        print("Migrations applied successfully.")
    except Exception as e:
        print(f"Error applying migrations: {e}")

    def run_qcluster():
        try:
            print("Starting background task worker (qcluster)...")
            call_command('qcluster')
        except Exception as e:
            print(f"Q Cluster Error: {e}")

    q_thread = threading.Thread(target=run_qcluster, daemon=True)
    q_thread.start()

    port = _reserve_port()
    _write_mcp_discovery(port)
    # Electron and MCP clients parse this exact URL shape.
    print(f"http://127.0.0.1:{port}")
    uvicorn.run(application, host="127.0.0.1", port=port)
