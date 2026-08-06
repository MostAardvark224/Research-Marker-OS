from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any

from api.utils import get_app_data_dir

DISCOVERY_FILENAME = "mcp_discovery.json"
TOKEN_FILENAME = "mcp_token"
DEFAULT_INSTRUCTIONS = (
    "You are connected to Research Marker on this machine. "
    "This works in normal Claude Desktop chat and in Claude Cowork. "
    "When the user asks you to use Research Marker / the Research Marker MCP, "
    "or mentions @page, @pages, @current, or @selection, "
    "call resolve_paper_question (or get_page / get_pages) to load the open paper's "
    "local context before answering. Prefer get_active_paper first if you need to "
    "know which document is open. Do not invent page content."
)


def discovery_path() -> Path:
    override = os.environ.get("RESEARCH_MARKER_MCP_DISCOVERY", "").strip()
    if override:
        return Path(override)
    return Path(get_app_data_dir()) / DISCOVERY_FILENAME


def token_path() -> Path:
    return Path(get_app_data_dir()) / TOKEN_FILENAME


def load_or_create_token() -> str:
    path = token_path()
    if path.is_file():
        token = path.read_text(encoding="utf-8").strip()
        if token:
            return token
    token = secrets.token_urlsafe(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return token


def regenerate_token() -> str:
    path = token_path()
    if path.exists():
        path.unlink()
    token = load_or_create_token()
    # Keep discovery file in sync if present.
    data = read_discovery()
    if data:
        data["token"] = token
        write_discovery_payload(data)
    return token


def write_discovery_payload(payload: dict[str, Any]) -> Path:
    path = discovery_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def write_discovery(*, port: int | str, host: str = "127.0.0.1") -> Path:
    port_int = int(port)
    base_url = f"http://{host}:{port_int}/api"
    payload = {
        "host": host,
        "port": port_int,
        "base_url": base_url,
        "token": load_or_create_token(),
        "discovery_path": str(discovery_path()),
    }
    return write_discovery_payload(payload)


def read_discovery() -> dict[str, Any] | None:
    path = discovery_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def resolve_command_and_args() -> tuple[str, list[str], dict[str, str]]:
    """Absolute command Claude Desktop should launch for the MCP stdio server."""
    import sys

    user_data = str(Path(get_app_data_dir()))
    discovery = str(discovery_path())
    env = {
        "RESEARCH_MARKER_MCP_DISCOVERY": discovery,
        "USER_DATA_DIR": user_data,
    }
    if getattr(sys, "frozen", False):
        return sys.executable, ["mcp"], env

    backend_root = Path(__file__).resolve().parents[2]
    env["PYTHONPATH"] = str(backend_root)
    env["DJANGO_SETTINGS_MODULE"] = "backend.settings"
    manage = backend_root / "manage.py"
    if manage.is_file():
        return sys.executable, [str(manage), "run_mcp"], env
    return sys.executable, ["-m", "api.mcp.server"], env


def build_claude_desktop_config() -> dict[str, Any]:
    command, args, env = resolve_command_and_args()
    return {
        "mcpServers": {
            "research-marker": {
                "command": command,
                "args": args,
                "env": env,
            }
        }
    }


def _port_is_open(port: int, host: str = "127.0.0.1") -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        try:
            return sock.connect_ex((host, int(port))) == 0
        except OSError:
            return False


def ensure_discovery_matches_live_backend() -> dict[str, Any] | None:
    """Repair discovery when it points at a closed local port.

    Uses TCP checks only (never HTTP). Calling our own Django runserver over HTTP
    from inside a request deadlocks the single-threaded dev server.
    """
    discovery = read_discovery()
    token = load_or_create_token()
    candidates: list[int] = []
    for value in (
        (discovery or {}).get("port"),
        os.environ.get("RESEARCH_MARKER_API_PORT"),
        os.environ.get("PORT"),
        8000,
        5000,
    ):
        try:
            port = int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if 1 <= port <= 65535 and port not in candidates:
            candidates.append(port)

    current = int((discovery or {}).get("port") or 0)
    if current and _port_is_open(current):
        if discovery and not discovery.get("token"):
            discovery["token"] = token
            write_discovery_payload(discovery)
        return discovery

    for port in candidates:
        if not _port_is_open(port):
            continue
        write_discovery(port=port, host="127.0.0.1")
        return read_discovery()
    return discovery


def setup_payload(*, port: int | None = None) -> dict[str, Any]:
    discovery = ensure_discovery_matches_live_backend()
    if discovery is None and port is not None:
        write_discovery(port=port)
        discovery = read_discovery()
    token = load_or_create_token()
    if discovery and not discovery.get("token"):
        discovery["token"] = token
        write_discovery_payload(discovery)
    return {
        "ready": bool(discovery and discovery.get("base_url")),
        "discovery_path": str(discovery_path()),
        "token": token,
        "base_url": (discovery or {}).get("base_url"),
        "port": (discovery or {}).get("port"),
        "claude_desktop_config": build_claude_desktop_config(),
        "instructions": DEFAULT_INSTRUCTIONS,
        "active_reader_path": str(Path(get_app_data_dir()) / "active_reader.json"),
    }
