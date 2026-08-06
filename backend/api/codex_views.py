from __future__ import annotations

import json

from django.http import StreamingHttpResponse
from django_q.tasks import async_task
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from api import models, serializers
from api.errors import DocumentNotFound, ResearchMarkerError
from api.paper_context.builder import build_paper_context
from api.paper_context.ingestion import clear_paper_context, ensure_document_ingested
from api.paper_context.retrieval import get_page, update_active_context
from api.paper_context.types import ContextLimits
from api.providers.codex import get_codex_provider
from api.user_preferences import deep_get, load_user_preferences


def _error_response(exc: Exception) -> Response:
    if isinstance(exc, ResearchMarkerError):
        return Response(exc.as_dict(), status=exc.http_status)
    return Response(
        {
            "error": "provider_unavailable",
            "message": "Codex could not complete the request.",
            "details": {"technical_message": str(exc)},
        },
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


def _context_limits() -> ContextLimits:
    prefs = load_user_preferences()
    values = deep_get(prefs, "context_limits", default={}) or {}

    def setting(name: str, default: int) -> int:
        try:
            return max(1, int(values.get(name, default)))
        except (TypeError, ValueError):
            return default

    return ContextLimits(
        maximum_explicit_pages=setting("maximum_explicit_pages", 20),
        maximum_retrieved_chunks=setting("maximum_retrieved_chunks", 6),
        maximum_text_characters=setting("maximum_text_characters", 48_000),
        maximum_page_images=setting("maximum_page_images", 4),
        maximum_image_bytes=setting("maximum_image_bytes", 8 * 1024 * 1024),
    )


def _optional_int(value):
    if value in (None, ""):
        return None
    return int(value)


def _as_bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


class CodexStatusView(APIView):
    def get(self, request):
        return Response(get_codex_provider().get_status())

    def post(self, request):
        provider = get_codex_provider()
        action = request.data.get("action", "connect")
        try:
            if action == "restart":
                payload = provider.restart()
            elif action == "disconnect":
                provider.disconnect()
                payload = provider.get_status()
            else:
                payload = provider.connect()
            return Response(payload)
        except Exception as exc:
            return _error_response(exc)


class CodexLoginView(APIView):
    def post(self, request):
        provider = get_codex_provider()
        try:
            mode = request.data.get("mode", "browser")
            payload = (
                provider.start_device_code_login()
                if mode == "device_code"
                else provider.start_chatgpt_login()
            )
            return Response(payload, status=status.HTTP_202_ACCEPTED)
        except Exception as exc:
            return _error_response(exc)

    def delete(self, request):
        get_codex_provider().cancel_login(str(request.data.get("login_id", "")))
        return Response(status=status.HTTP_204_NO_CONTENT)


class CodexLogoutView(APIView):
    def post(self, request):
        try:
            get_codex_provider().logout()
            return Response(get_codex_provider().get_status())
        except Exception as exc:
            return _error_response(exc)


class CodexRateLimitsView(APIView):
    def get(self, request):
        try:
            return Response({"rate_limits": get_codex_provider().rate_limits()})
        except Exception as exc:
            return _error_response(exc)


class CodexModelsView(APIView):
    def get(self, request):
        try:
            return Response({"models": get_codex_provider().models()})
        except Exception as exc:
            return _error_response(exc)


class CodexConversationsView(APIView):
    def get(self, request):
        return Response({"conversations": get_codex_provider().list_conversations()})

    def post(self, request):
        try:
            document_id = int(request.data.get("document_id"))
            if not models.Document.objects.filter(pk=document_id).exists():
                raise DocumentNotFound(f"Document {document_id} was not found.")
            conversation = get_codex_provider().create_conversation(
                document_id,
                str(request.data.get("title", "")),
            )
            return Response(
                serializers.ChatLogSerializer(conversation).data,
                status=status.HTTP_201_CREATED,
            )
        except Exception as exc:
            return _error_response(exc)


class CodexConversationDetailView(APIView):
    def get(self, request, conversation_id):
        try:
            conversation = models.ChatLogs.objects.get(pk=conversation_id, provider="codex")
            return Response(serializers.ChatLogSerializer(conversation).data)
        except models.ChatLogs.DoesNotExist:
            return Response(
                {"error": "conversation_not_found", "message": "Conversation not found."},
                status=status.HTTP_404_NOT_FOUND,
            )


def _codex_model(request) -> str | None:
    model = str(request.data.get("model", "")).strip()
    if model:
        return model
    prefs = load_user_preferences()
    saved = (
        prefs.get("user_preferences", {})
        .get("ai", {})
        .get("models", {})
        .get("codex", "")
    )
    if saved:
        return str(saved).strip() or None
    try:
        return get_codex_provider().default_model()
    except Exception:
        return None


class CodexConversationStreamView(APIView):
    def post(self, request, conversation_id):
        try:
            conversation = models.ChatLogs.objects.select_related("document").get(
                pk=conversation_id,
                provider="codex",
            )
            question = str(request.data.get("question", ""))
            context = build_paper_context(
                document_id=conversation.document_id,
                question=question,
                current_page=_optional_int(request.data.get("current_page")),
                selected_text=str(request.data.get("selected_text", "")),
                selected_text_page=_optional_int(request.data.get("selected_text_page")),
                include_page_image=_as_bool(request.data.get("include_page_image", False)),
                limits=_context_limits(),
            )
            provider = get_codex_provider()
            event_stream = provider.send_message(
                conversation.id,
                question,
                context,
                model=_codex_model(request),
            )
        except models.ChatLogs.DoesNotExist:
            return Response(
                {"error": "conversation_not_found", "message": "Conversation not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as exc:
            return _error_response(exc)

        def stream():
            try:
                for event in event_stream:
                    yield json.dumps(event, separators=(",", ":")) + "\n"
            except Exception as exc:
                if isinstance(exc, ResearchMarkerError):
                    payload = exc.as_dict()
                else:
                    message = str(exc).strip() or "Codex generation failed."
                    payload = {
                        "error": "provider_unavailable",
                        "message": message,
                        "details": {"technical_message": message},
                    }
                yield json.dumps({"type": "error", **payload}, separators=(",", ":")) + "\n"

        response = StreamingHttpResponse(stream(), content_type="application/x-ndjson")
        response["Cache-Control"] = "no-cache, no-transform"
        response["X-Accel-Buffering"] = "no"
        return response


class CodexConversationCancelView(APIView):
    def post(self, request, conversation_id):
        try:
            get_codex_provider().cancel_generation(conversation_id)
            return Response({"status": "cancelling"})
        except Exception as exc:
            return _error_response(exc)


class PaperContextStatusView(APIView):
    def get(self, request, document_id):
        try:
            document = models.Document.objects.get(pk=document_id)
        except models.Document.DoesNotExist:
            return _error_response(DocumentNotFound(f"Document {document_id} was not found."))
        return Response(
            {
                "document_id": document.id,
                "document_hash": document.document_hash,
                "status": document.context_status,
                "error": document.context_error,
                "page_count": document.page_count,
                "updated_at": document.context_updated_at,
            }
        )

    def post(self, request, document_id):
        try:
            document = models.Document.objects.get(pk=document_id)
        except models.Document.DoesNotExist:
            return _error_response(DocumentNotFound(f"Document {document_id} was not found."))
        if document.ocr_status in (
            models.Document.OcrStatus.QUEUED,
            models.Document.OcrStatus.PROCESSING,
        ):
            return Response(
                {
                    "error": "ocr_in_progress",
                    "message": "Context ingestion will start after OCR finishes.",
                },
                status=status.HTTP_409_CONFLICT,
            )
        document.context_status = "queued"
        document.context_error = ""
        document.save(update_fields=["context_status", "context_error"])
        async_task(
            "api.paper_context.ingestion.ingest_document",
            document.id,
            force=bool(request.data.get("force", False)),
        )
        return Response({"status": "queued"}, status=status.HTTP_202_ACCEPTED)


class PaperContextPageView(APIView):
    def get(self, request, document_id, page_number):
        try:
            page = get_page(
                document_id,
                page_number,
                include_image=False,
            )
            return Response(page.to_dict(expose_local_path=False))
        except Exception as exc:
            return _error_response(exc)


class PaperContextPreviewView(APIView):
    def post(self, request, document_id):
        try:
            context = build_paper_context(
                document_id=document_id,
                question=str(request.data.get("question", "")),
                current_page=_optional_int(request.data.get("current_page")),
                selected_text=str(request.data.get("selected_text", "")),
                selected_text_page=_optional_int(request.data.get("selected_text_page")),
                include_page_image=_as_bool(request.data.get("include_page_image", False)),
                limits=_context_limits(),
            )
            return Response(context.to_dict(expose_local_paths=False))
        except Exception as exc:
            return _error_response(exc)


class PaperContextClearView(APIView):
    def post(self, request):
        try:
            include_ai_sessions = _as_bool(request.data.get("include_ai_sessions", True))
            return Response(clear_paper_context(include_ai_sessions=include_ai_sessions))
        except Exception as exc:
            return _error_response(exc)


class ActiveContextView(APIView):
    def get(self, request):
        from api.paper_context.retrieval import get_active_context, get_active_document

        state = get_active_context()
        document = get_active_document()
        return Response(
            {
                "document_id": state.document_id,
                "document_title": state.document_title
                or (document or {}).get("document_title", ""),
                "current_page": state.current_page,
                "selected_text_page": state.selected_text_page,
                "has_selection": bool(state.selected_text),
                "page_count": (document or {}).get("page_count"),
                "last_updated": state.last_updated,
            }
        )

    def post(self, request):
        state = update_active_context(
            document_id=_optional_int(request.data.get("document_id")),
            document_title=str(request.data.get("document_title", "")),
            current_page=_optional_int(request.data.get("current_page")),
            selected_text=str(request.data.get("selected_text", "")),
            selected_text_page=_optional_int(request.data.get("selected_text_page")),
        )
        return Response(
            {
                "document_id": state.document_id,
                "document_title": state.document_title,
                "current_page": state.current_page,
                "selected_text_page": state.selected_text_page,
                "last_updated": state.last_updated,
            }
        )
