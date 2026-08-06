from __future__ import annotations

from functools import wraps
from typing import Callable

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.errors import ResearchMarkerError
from api.mcp.discovery import (
    build_claude_desktop_config,
    load_or_create_token,
    read_discovery,
    regenerate_token,
    setup_payload,
    write_discovery,
)
from api.mcp import tools as mcp_tools


def _client_host(request: Request) -> str:
    return (
        request.META.get("REMOTE_ADDR")
        or request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
        or ""
    )


def _is_loopback(request: Request) -> bool:
    host = _client_host(request)
    return host in {"127.0.0.1", "::1", "localhost"}


def _extract_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return (
        request.headers.get("X-Research-Marker-Token", "")
        or str(request.query_params.get("token", "")).strip()
    )


def require_mcp_token(view_method: Callable):
    @wraps(view_method)
    def wrapper(self, request: Request, *args, **kwargs):
        if not _is_loopback(request):
            return Response(
                {
                    "error": "forbidden",
                    "message": "Research Marker MCP is only available on localhost.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        expected = load_or_create_token()
        provided = _extract_token(request)
        if not provided or provided != expected:
            return Response(
                {
                    "error": "unauthorized",
                    "message": "Missing or invalid Research Marker MCP token.",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return view_method(self, request, *args, **kwargs)

    return wrapper


def _error_response(exc: Exception) -> Response:
    if isinstance(exc, ResearchMarkerError):
        return Response(exc.as_dict(), status=exc.http_status)
    return Response(
        {
            "error": "mcp_tool_failed",
            "message": str(exc) or "The MCP tool request failed.",
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


def _optional_int(value):
    if value in (None, ""):
        return None
    return int(value)


def _as_bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


class McpSetupView(APIView):
    """Settings UI: discovery + Claude Desktop config (loopback only)."""

    def get(self, request):
        if not _is_loopback(request):
            return Response(
                {"error": "forbidden", "message": "MCP setup is localhost-only."},
                status=status.HTTP_403_FORBIDDEN,
            )
        # Do not rewrite discovery from the HTTP request port — browser/proxy Host
        # headers have repeatedly published stale ports (e.g. 5000) and broken Claude.
        # Discovery is owned by runserver/main.py startup + explicit refresh_discovery.
        from api.mcp.discovery import ensure_discovery_matches_live_backend

        ensure_discovery_matches_live_backend()
        payload = setup_payload()
        payload["claude_desktop_config_json"] = __import__("json").dumps(
            build_claude_desktop_config(),
            indent=2,
        )
        return Response(payload)

    def post(self, request):
        if not _is_loopback(request):
            return Response(
                {"error": "forbidden", "message": "MCP setup is localhost-only."},
                status=status.HTTP_403_FORBIDDEN,
            )
        action = str(request.data.get("action", "")).strip().lower()
        if action == "regenerate_token":
            token = regenerate_token()
            from api.mcp.discovery import ensure_discovery_matches_live_backend

            ensure_discovery_matches_live_backend()
            payload = setup_payload()
            payload["token"] = token
            payload["claude_desktop_config_json"] = __import__("json").dumps(
                build_claude_desktop_config(),
                indent=2,
            )
            return Response(payload)
        if action == "refresh_discovery":
            port = _optional_int(request.data.get("port")) or 8000
            write_discovery(port=port, host="127.0.0.1")
            from api.mcp.discovery import ensure_discovery_matches_live_backend

            ensure_discovery_matches_live_backend()
            payload = setup_payload(port=int(port))
            payload["claude_desktop_config_json"] = __import__("json").dumps(
                build_claude_desktop_config(),
                indent=2,
            )
            return Response(payload)
        return Response(
            {"error": "unknown_action", "message": "Supported actions: regenerate_token, refresh_discovery."},
            status=status.HTTP_400_BAD_REQUEST,
        )


class McpActivePaperView(APIView):
    @require_mcp_token
    def get(self, request):
        try:
            return Response(mcp_tools.active_paper_payload())
        except Exception as exc:
            return _error_response(exc)


class McpPageView(APIView):
    @require_mcp_token
    def get(self, request):
        try:
            return Response(
                mcp_tools.page_payload(
                    page_number=_optional_int(request.query_params.get("page")),
                    document_id=_optional_int(request.query_params.get("document_id")),
                    include_image=_as_bool(request.query_params.get("include_image", False)),
                )
            )
        except Exception as exc:
            return _error_response(exc)


class McpPagesView(APIView):
    @require_mcp_token
    def get(self, request):
        try:
            start = _optional_int(request.query_params.get("start"))
            end = _optional_int(request.query_params.get("end"))
            if start is None or end is None:
                raise ResearchMarkerError("Provide both start and end page numbers.")
            return Response(
                mcp_tools.pages_payload(
                    start_page=start,
                    end_page=end,
                    document_id=_optional_int(request.query_params.get("document_id")),
                    include_images=_as_bool(request.query_params.get("include_images", False)),
                )
            )
        except Exception as exc:
            return _error_response(exc)


class McpSelectionView(APIView):
    @require_mcp_token
    def get(self, request):
        try:
            return Response(mcp_tools.selection_payload())
        except Exception as exc:
            return _error_response(exc)


class McpSearchView(APIView):
    @require_mcp_token
    def get(self, request):
        try:
            query = str(request.query_params.get("query", "")).strip()
            if not query:
                raise ResearchMarkerError("Provide a search query.")
            return Response(
                mcp_tools.search_payload(
                    query=query,
                    document_id=_optional_int(request.query_params.get("document_id")),
                    limit=_optional_int(request.query_params.get("limit")) or 6,
                )
            )
        except Exception as exc:
            return _error_response(exc)


class McpResolveView(APIView):
    @require_mcp_token
    def post(self, request):
        try:
            question = str(request.data.get("question", "")).strip()
            if not question:
                raise ResearchMarkerError("Provide a question that may include @page mentions.")
            return Response(
                mcp_tools.resolve_question_payload(
                    question=question,
                    document_id=_optional_int(request.data.get("document_id")),
                    include_page_image=_as_bool(request.data.get("include_page_image", True)),
                )
            )
        except Exception as exc:
            return _error_response(exc)
