from __future__ import annotations

"""Stdio MCP server for Claude Desktop / Cowork.

Talks to the running Research Marker backend over loopback HTTP so it shares
the same in-memory active-reader state as the PDF viewer.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

# Ensure Django settings are importable when launched as a frozen binary or -m module.
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")


def _load_discovery() -> dict[str, Any]:
    from api.mcp.discovery import load_or_create_token, read_discovery

    data = read_discovery()
    if not data or not data.get("base_url"):
        raise RuntimeError(
            "Research Marker is not running or MCP discovery is missing. "
            "Open Research Marker, then retry from Claude Desktop chat or Cowork."
        )
    if not data.get("token"):
        data["token"] = load_or_create_token()
    return data


def _candidate_ports(discovery: dict[str, Any]) -> list[int]:
    ports: list[int] = []
    for value in (
        discovery.get("port"),
        os.environ.get("RESEARCH_MARKER_API_PORT"),
        os.environ.get("PORT"),
        8000,
        5000,
    ):
        try:
            port = int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if 1 <= port <= 65535 and port not in ports:
            ports.append(port)
    return ports


def _probe_live_backend(discovery: dict[str, Any]) -> dict[str, Any]:
    """If discovery points at a dead port, find a live local backend and rewrite it."""
    from api.mcp.discovery import load_or_create_token, read_discovery, write_discovery

    token = str(discovery.get("token") or load_or_create_token())
    for port in _candidate_ports(discovery):
        base_url = f"http://127.0.0.1:{port}/api"
        try:
            with httpx.Client(timeout=2.0) as client:
                response = client.get(
                    f"{base_url}/mcp/tools/active/",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "X-Research-Marker-Token": token,
                    },
                )
            # Auth may fail if tokens diverged; setup is enough to prove the port is live.
            if response.status_code in (200, 401):
                if int(discovery.get("port") or 0) != port:
                    write_discovery(port=port, host="127.0.0.1")
                    healed = read_discovery()
                    if healed:
                        return healed
                return discovery
        except httpx.HTTPError:
            continue
    return discovery


def _request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    discovery = _probe_live_backend(_load_discovery())
    url = discovery["base_url"].rstrip("/") + path
    headers = {
        "Authorization": f"Bearer {discovery['token']}",
        "X-Research-Marker-Token": discovery["token"],
    }
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.request(
                method,
                url,
                params=params,
                json=json_body,
                headers=headers,
            )
    except httpx.HTTPError as exc:
        # One more heal+retry in case the backend came up on another port mid-call.
        discovery = _probe_live_backend(_load_discovery())
        url = discovery["base_url"].rstrip("/") + path
        headers = {
            "Authorization": f"Bearer {discovery['token']}",
            "X-Research-Marker-Token": discovery["token"],
        }
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    headers=headers,
                )
        except httpx.HTTPError as retry_exc:
            raise RuntimeError(
                "Could not reach the Research Marker backend at "
                f"{discovery.get('base_url')}. "
                "Make sure the dev backend/app is running, open Settings → "
                "AI Preferences → Claude Desktop / Cowork → Refresh status, "
                "then fully quit and reopen Claude Desktop so MCP reloads."
            ) from retry_exc
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"Research Marker returned a non-JSON response (HTTP {response.status_code})."
        ) from exc
    if response.status_code >= 400:
        message = payload.get("message") if isinstance(payload, dict) else None
        raise RuntimeError(message or f"Research Marker MCP error (HTTP {response.status_code}).")
    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected MCP tool response shape.")
    return payload


def _json_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _with_images(payload: dict[str, Any], image_keys: list[str] | None = None):
    """Return text plus optional MCP Image objects from base64 payloads."""
    from mcp.server.mcpserver import Image

    images: list[Image] = []
    if "image" in payload and isinstance(payload.get("image"), dict):
        image = payload["image"]
        if image.get("base64"):
            images.append(
                Image(
                    data=__import__("base64").b64decode(image["base64"]),
                    format="png",
                )
            )
        # Keep path metadata; drop bulky base64 from the text half.
        slim = dict(payload)
        slim["image"] = {
            "path": image.get("path"),
            "mime_type": image.get("mime_type"),
            "byte_size": image.get("byte_size"),
            "attached": True,
        }
        payload = slim
    if "images" in payload and isinstance(payload.get("images"), list):
        slim_images = []
        for image in payload["images"]:
            if not isinstance(image, dict):
                continue
            if image.get("base64"):
                images.append(
                    Image(
                        data=__import__("base64").b64decode(image["base64"]),
                        format="png",
                    )
                )
            slim_images.append(
                {
                    "path": image.get("path"),
                    "mime_type": image.get("mime_type"),
                    "byte_size": image.get("byte_size"),
                    "attached": bool(image.get("base64")),
                }
            )
        payload = dict(payload)
        payload["images"] = slim_images

    text = _json_text(payload)
    if not images:
        return text
    return [text, *images]


def build_server():
    from mcp.server.mcpserver import MCPServer

    from api.mcp.discovery import DEFAULT_INSTRUCTIONS

    server = MCPServer(
        name="research-marker",
        title="Research Marker",
        instructions=DEFAULT_INSTRUCTIONS,
    )

    @server.tool(
        description=(
            "Return the paper currently open in Research Marker (document id, title, "
            "current page, selection flags). Call this before answering questions about "
            "'this page' or '@page' when you are unsure what is open."
        )
    )
    def get_active_paper() -> str:
        return _json_text(_request("GET", "/mcp/tools/active/"))

    @server.tool(
        description=(
            "Load one page of the active (or specified) paper. Omit page_number to use "
            "the viewer's current page. Set include_image=true for diagrams/figures."
        )
    )
    def get_page(
        page_number: int | None = None,
        document_id: int | None = None,
        include_image: bool = False,
    ):
        params: dict[str, Any] = {"include_image": str(include_image).lower()}
        if page_number is not None:
            params["page"] = page_number
        if document_id is not None:
            params["document_id"] = document_id
        return _with_images(_request("GET", "/mcp/tools/page/", params=params))

    @server.tool(
        description=(
            "Load an inclusive page range from the active paper. Use for @pages 4-7 style "
            "requests. include_images attaches page renders when helpful for figures."
        )
    )
    def get_pages(
        start_page: int,
        end_page: int,
        document_id: int | None = None,
        include_images: bool = False,
    ):
        params: dict[str, Any] = {
            "start": start_page,
            "end": end_page,
            "include_images": str(include_images).lower(),
        }
        if document_id is not None:
            params["document_id"] = document_id
        payload = _request("GET", "/mcp/tools/pages/", params=params)
        # Flatten page images for MCP image attachments.
        images = []
        for page in payload.get("pages") or []:
            image = page.get("image")
            if isinstance(image, dict) and image.get("base64"):
                images.append(image)
                page["image"] = {
                    "path": image.get("path"),
                    "mime_type": image.get("mime_type"),
                    "byte_size": image.get("byte_size"),
                    "attached": True,
                }
        if images:
            payload = dict(payload)
            payload["images"] = images
        return _with_images(payload)

    @server.tool(
        description="Return the text currently selected in the Research Marker PDF viewer, if any."
    )
    def get_selection() -> str:
        return _json_text(_request("GET", "/mcp/tools/selection/"))

    @server.tool(
        description=(
            "Search the active paper's extracted text/chunks (local FTS). Use when the user "
            "asks about a topic without naming a page."
        )
    )
    def search_paper(
        query: str,
        document_id: int | None = None,
        limit: int = 6,
    ) -> str:
        params: dict[str, Any] = {"query": query, "limit": limit}
        if document_id is not None:
            params["document_id"] = document_id
        return _json_text(_request("GET", "/mcp/tools/search/", params=params))

    @server.tool(
        description=(
            "Resolve a user question the same way Research Marker's in-app chat does, "
            "including @page / @pages / @current / @selection mentions. Returns formatted "
            "paper context and optional page images. Prefer this for questions like "
            "'Explain the diagram on @page'."
        )
    )
    def resolve_paper_question(
        question: str,
        document_id: int | None = None,
        include_page_image: bool = True,
    ):
        body: dict[str, Any] = {
            "question": question,
            "include_page_image": include_page_image,
        }
        if document_id is not None:
            body["document_id"] = document_id
        return _with_images(_request("POST", "/mcp/tools/resolve/", json_body=body))

    return server


def main() -> None:
    # Discovery helpers import api.utils (no Django required after utils lazy-import).
    # Tool calls are pure HTTP against the running Research Marker backend.
    server = build_server()
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
