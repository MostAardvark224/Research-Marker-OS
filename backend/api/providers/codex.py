from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
import importlib.metadata
import json
import logging
from pathlib import Path
import shutil
from threading import RLock, Thread
from typing import Any
from uuid import uuid4

from django.utils import timezone as django_timezone

from api import models
from api.errors import (
    GenerationCancelled,
    ProviderAuthenticationExpired,
    ProviderNotAuthenticated,
    ProviderNotInstalled,
    ProviderRateLimited,
    ProviderUnavailable,
)
from api.paper_context.builder import format_paper_context
from api.paper_context.citations import extract_citations
from api.paper_context.types import PaperContext
from api.utils import get_app_data_dir
from .base import AIProvider

try:
    from openai_codex import ApprovalMode, Codex, CodexConfig, Sandbox
    from openai_codex.generated.v2_all import GetAccountRateLimitsResponse
except ImportError:  # Packaged builds surface an actionable Not Installed state.
    ApprovalMode = Codex = CodexConfig = Sandbox = None
    GetAccountRateLimitsResponse = None

LOGGER = logging.getLogger(__name__)
SESSION_RETENTION_HOURS = 24


def _sdk_missing_message() -> str:
    import sys

    if getattr(sys, "frozen", False):
        return (
            "The Codex runtime is missing from this installation. "
            "Reinstall Research Marker to restore it."
        )
    return (
        "Codex is not installed in this Python environment. "
        "Run `pip install -r requirements.txt` in the backend folder and restart the app."
    )

PAPER_DEVELOPER_INSTRUCTIONS = """You are the embedded paper-reading assistant.
Answer the user's research-paper question directly from the supplied context.
Do not run shell commands, inspect files, edit files, or use external network resources.
Do not ask for permissions. The context and any page images are already attached.
Follow the citation and evidence rules in the supplied paper instructions."""

SMART_COLLECTION_INSTRUCTIONS = """You label and advise on research-note clusters.
Return exactly what the user asks for. Prefer valid JSON when requested.
Do not run shell commands, inspect files, edit files, or use external network resources.
Do not ask for permissions."""

READ_ONLY_SANDBOX_POLICY = {
    "type": "readOnly",
    "networkAccess": False,
}


def _codex_error_message(error: Any) -> str:
    if error is None:
        return ""
    for attr in ("message", "detail", "code"):
        value = getattr(error, attr, None)
        if value:
            return str(value)
    return str(error)


class CodexProvider(AIProvider):
    def __init__(self) -> None:
        self._sdk: Any = None
        self._lock = RLock()
        self._active_turns: dict[int, tuple[str, str]] = {}
        self._login_handles: dict[str, Any] = {}
        self._last_error = ""

    @property
    def sdk_version(self) -> str | None:
        try:
            return importlib.metadata.version("openai-codex")
        except importlib.metadata.PackageNotFoundError:
            return None

    def _require_sdk(self) -> Any:
        if Codex is None:
            raise ProviderNotInstalled(_sdk_missing_message())
        if self._sdk is None:
            self.connect()
        return self._sdk

    def connect(self) -> dict[str, Any]:
        with self._lock:
            if self._sdk is not None:
                return self.get_status()
            if Codex is None:
                return self.get_status()
            try:
                config = CodexConfig(
                    client_name="research_marker",
                    client_title="Research Marker",
                    client_version="1.1.3",
                    experimental_api=True,
                )
                self._sdk = Codex(config)
                self._last_error = ""
            except (FileNotFoundError, ImportError) as exc:
                self._last_error = str(exc)
                raise ProviderNotInstalled(
                    "The Codex runtime could not be started. Reinstall the application."
                ) from exc
            except Exception as exc:
                self._last_error = str(exc)
                raise ProviderUnavailable(
                    "The local Codex runtime failed to start. Try Restart Codex."
                ) from exc
        self.cleanup_sessions()
        return self.get_status()

    def disconnect(self) -> None:
        with self._lock:
            sdk, self._sdk = self._sdk, None
            self._active_turns.clear()
        if sdk is not None:
            try:
                sdk.close()
            except Exception:
                LOGGER.exception("Codex runtime did not close cleanly")

    def restart(self) -> dict[str, Any]:
        self.disconnect()
        return self.connect()

    def _account_payload(self) -> tuple[dict | None, bool]:
        sdk = self._require_sdk()
        response = sdk.account(refresh_token=False)
        if response.account is None:
            return None, bool(response.requires_openai_auth)
        root = response.account.root
        return root.model_dump(by_alias=True, mode="json"), bool(response.requires_openai_auth)

    def get_status(self) -> dict[str, Any]:
        if Codex is None:
            return {
                "state": "not_installed",
                "installed": False,
                "connected": False,
                "sdk_version": None,
                "message": _sdk_missing_message(),
            }
        if self._sdk is None:
            return {
                "state": "not_connected",
                "installed": True,
                "connected": False,
                "sdk_version": self.sdk_version,
            }
        try:
            process = getattr(getattr(self._sdk, "_client", None), "_proc", None)
            if process is not None and process.poll() is not None:
                self.disconnect()
                return {
                    "state": "runtime_error",
                    "installed": True,
                    "connected": False,
                    "sdk_version": self.sdk_version,
                    "message": "The Codex process exited unexpectedly. Restart Codex.",
                }
            account, requires_auth = self._account_payload()
            if not account:
                return {
                    "state": "authentication_required" if requires_auth else "connected",
                    "installed": True,
                    "connected": True,
                    "authenticated": False,
                    "sdk_version": self.sdk_version,
                    "message": (
                        "Open Settings → AI Preferences and sign in with ChatGPT to use Codex."
                        if requires_auth
                        else None
                    ),
                }
            account_type = account.get("type")
            is_chatgpt = account_type == "chatgpt"
            return {
                "state": "connected" if is_chatgpt else "api_key_mode",
                "installed": True,
                "connected": True,
                "authenticated": True,
                "subscription_usable": is_chatgpt,
                "auth_mode": account_type,
                "email": account.get("email"),
                "plan_type": account.get("planType"),
                "sdk_version": self.sdk_version,
                "message": (
                    None
                    if is_chatgpt
                    else "Codex is authenticated with an API key. Subscription mode will not use it."
                ),
            }
        except Exception as exc:
            message = str(exc)
            lowered = message.lower()
            if "expired" in lowered or "unauthorized" in lowered:
                state = "authentication_expired"
            else:
                state = "runtime_error"
            return {
                "state": state,
                "installed": True,
                "connected": False,
                "sdk_version": self.sdk_version,
                "message": "Codex authentication failed. Sign in again." if state == "authentication_expired" else "Codex is unavailable. Restart the runtime.",
            }

    def _ensure_chatgpt_account(self) -> None:
        status = self.get_status()
        if status.get("state") == "authentication_expired":
            raise ProviderAuthenticationExpired("Codex authentication expired. Sign in again.")
        if status.get("auth_mode") == "apiKey":
            raise ProviderNotAuthenticated(
                "Codex is using API-key billing. Sign in with ChatGPT to use your Codex subscription."
            )
        if not status.get("subscription_usable"):
            raise ProviderNotAuthenticated("Connect Codex with your ChatGPT account first.")

    def _watch_login(self, handle: Any) -> None:
        try:
            result = handle.wait()
            if not result.success:
                self._last_error = result.error or "Codex login failed."
        except Exception as exc:
            self._last_error = str(exc)
        finally:
            self._login_handles.pop(handle.login_id, None)

    def start_chatgpt_login(self) -> dict[str, Any]:
        if Codex is None:
            raise ProviderNotInstalled(_sdk_missing_message())
        handle = self._require_sdk().login_chatgpt()
        self._login_handles[handle.login_id] = handle
        Thread(target=self._watch_login, args=(handle,), daemon=True).start()
        return {"login_id": handle.login_id, "auth_url": handle.auth_url, "type": "chatgpt"}

    def start_device_code_login(self) -> dict[str, Any]:
        if Codex is None:
            raise ProviderNotInstalled(_sdk_missing_message())
        handle = self._require_sdk().login_chatgpt_device_code()
        self._login_handles[handle.login_id] = handle
        Thread(target=self._watch_login, args=(handle,), daemon=True).start()
        return {
            "login_id": handle.login_id,
            "verification_url": handle.verification_url,
            "user_code": handle.user_code,
            "type": "chatgptDeviceCode",
        }

    def cancel_login(self, login_id: str) -> None:
        handle = self._login_handles.get(login_id)
        if handle is not None:
            handle.cancel()

    def logout(self) -> None:
        sdk = self._require_sdk()
        sdk.logout()

    def rate_limits(self) -> dict[str, Any] | None:
        self._ensure_chatgpt_account()
        sdk = self._require_sdk()
        client = getattr(sdk, "_client", None)
        if client is None or GetAccountRateLimitsResponse is None:
            return None
        try:
            response = client.request(
                "account/rateLimits/read",
                None,
                response_model=GetAccountRateLimitsResponse,
            )
            return response.model_dump(by_alias=True, mode="json")
        except Exception as exc:
            LOGGER.info("Codex rate-limit data unavailable: %s", exc)
            return None

    def models(self) -> list[dict[str, Any]]:
        catalog = self._require_sdk().models()
        return [
            {
                "id": item.model,
                "display_name": item.display_name,
                "description": item.description,
                "is_default": item.is_default,
                "input_modalities": item.input_modalities,
            }
            for item in catalog.data
            if not item.hidden
        ]

    def default_model(self) -> str | None:
        catalog = self.models()
        defaults = [item["id"] for item in catalog if item.get("is_default")]
        if defaults:
            return defaults[0]
        return catalog[0]["id"] if catalog else None

    def _conversation_dir(self, conversation_id: int) -> Path:
        return Path(get_app_data_dir()) / "ai_sessions" / str(conversation_id)

    def _prepare_session(self, conversation_id: int, context: PaperContext) -> tuple[Path, list[str]]:
        session_dir = self._conversation_dir(conversation_id)
        images_dir = session_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        prompt = format_paper_context(context)
        (session_dir / "context.txt").write_text(prompt, encoding="utf-8")
        (session_dir / "metadata.json").write_text(
            json.dumps(
                {
                    "document_id": context.document_id,
                    "document_title": context.document_title,
                    "referenced_pages": context.referenced_pages,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        local_images: list[str] = []
        for source in context.page_images:
            source_path = Path(source)
            if not source_path.is_file():
                continue
            destination = images_dir / source_path.name
            shutil.copy2(source_path, destination)
            local_images.append(str(destination.resolve()))
        return session_dir, local_images

    def create_conversation(
        self,
        document_id: int,
        title: str = "",
        *,
        model: str | None = None,
    ) -> models.ChatLogs:
        self._ensure_chatgpt_account()
        document = models.Document.objects.get(pk=document_id)
        conversation = models.ChatLogs.objects.create(
            name=(title or f"{document.title} discussion")[:255],
            content=[],
            provider="codex",
            document=document,
        )
        session_dir = self._conversation_dir(conversation.id)
        session_dir.mkdir(parents=True, exist_ok=True)
        try:
            thread = self._require_sdk().thread_start(
                approval_mode=ApprovalMode.deny_all,
                cwd=str(session_dir.resolve()),
                developer_instructions=PAPER_DEVELOPER_INSTRUCTIONS,
                model=model or self.default_model(),
                sandbox=Sandbox.read_only,
                service_name="research_marker",
            )
            conversation.codex_thread_id = thread.id
            conversation.save(update_fields=["codex_thread_id"])
            return conversation
        except Exception:
            conversation.delete()
            raise

    def resume_conversation(self, conversation_id: int) -> Any:
        self._ensure_chatgpt_account()
        try:
            conversation = models.ChatLogs.objects.get(pk=conversation_id, provider="codex")
        except models.ChatLogs.DoesNotExist as exc:
            raise ProviderUnavailable("The Codex conversation was not found.") from exc
        if not conversation.codex_thread_id:
            raise ProviderUnavailable("This conversation has no Codex thread to resume.")
        session_dir = self._conversation_dir(conversation.id)
        session_dir.mkdir(parents=True, exist_ok=True)
        return self._require_sdk().thread_resume(
            conversation.codex_thread_id,
            approval_mode=ApprovalMode.deny_all,
            cwd=str(session_dir.resolve()),
            developer_instructions=PAPER_DEVELOPER_INSTRUCTIONS,
            sandbox=Sandbox.read_only,
        )

    def _append_message(
        self,
        conversation: models.ChatLogs,
        *,
        role: str,
        content: str,
        citations: list[dict] | None = None,
        status: str = "complete",
    ) -> None:
        messages = list(conversation.content or [])
        messages.append(
            {
                "role": role,
                "content": content,
                "timestamp": django_timezone.now().isoformat(),
                "citations": citations or [],
                "status": status,
            }
        )
        conversation.content = messages
        conversation.save(update_fields=["content", "updated_at"])

    def send_message(
        self,
        conversation_id: int,
        question: str,
        paper_context: PaperContext,
        *,
        model: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        self._ensure_chatgpt_account()
        try:
            conversation = models.ChatLogs.objects.select_related("document").get(
                pk=conversation_id,
                provider="codex",
            )
        except models.ChatLogs.DoesNotExist as exc:
            raise ProviderUnavailable("The Codex conversation was not found.") from exc
        if conversation.document_id != paper_context.document_id:
            raise ProviderUnavailable("The conversation belongs to a different paper.")
        if not conversation.codex_thread_id:
            raise ProviderUnavailable("This conversation has no Codex thread to resume.")
        session_dir, images = self._prepare_session(conversation_id, paper_context)
        prompt = format_paper_context(paper_context)
        wire_input = [{"type": "text", "text": prompt}]
        wire_input.extend({"type": "localImage", "path": path} for path in images)
        sdk = self._require_sdk()
        client = getattr(sdk, "_client", None)
        if client is None:
            raise ProviderUnavailable("The installed Codex SDK does not expose a turn transport.")
        thread_id = conversation.codex_thread_id

        self._append_message(conversation, role="user", content=question)
        turn_params: dict[str, Any] = {
            "cwd": str(session_dir.resolve()),
            "approvalPolicy": "never",
            "sandboxPolicy": READ_ONLY_SANDBOX_POLICY,
        }
        resolved_model = model or self.default_model()
        if resolved_model:
            turn_params["model"] = resolved_model
        try:
            started = client.turn_start(
                thread_id,
                wire_input,
                params=turn_params,
            )
            turn_id = started.turn.id
            self._active_turns[conversation_id] = (thread_id, turn_id)
            client.register_turn_notifications(turn_id)
            answer_parts: list[str] = []
            yield {"type": "started", "turn_id": turn_id}
            try:
                while True:
                    notification = client.next_turn_notification(turn_id)
                    if notification.method == "item/agentMessage/delta":
                        delta = notification.payload.delta
                        answer_parts.append(delta)
                        yield {"type": "delta", "text": delta}
                    elif notification.method == "turn/completed":
                        status = str(notification.payload.turn.status.value)
                        if status == "interrupted":
                            raise GenerationCancelled("Codex generation was cancelled.")
                        if status == "failed":
                            error = notification.payload.turn.error
                            message = _codex_error_message(error) or "Codex generation failed."
                            if "rate" in message.lower() and "limit" in message.lower():
                                raise ProviderRateLimited(message)
                            raise ProviderUnavailable(message)
                        break
            finally:
                client.unregister_turn_notifications(turn_id)

            answer = "".join(answer_parts).strip()
            allowed_pages = {
                page.page_number for page in paper_context.page_text
            } | {
                page
                for chunk in paper_context.retrieved_chunks
                for page in range(chunk.start_page, chunk.end_page + 1)
            }
            citations = [
                item.to_dict()
                for item in extract_citations(
                    answer,
                    document_id=paper_context.document_id,
                    allowed_pages=allowed_pages,
                )
            ]
            self._append_message(
                conversation,
                role="model",
                content=answer,
                citations=citations,
            )
            yield {"type": "completed", "citations": citations}
        except GenerationCancelled:
            yield {"type": "cancelled"}
        except Exception as exc:
            LOGGER.warning("Codex generation failed for conversation %s: %s", conversation_id, exc)
            lowered = str(exc).lower()
            if "rate limit" in lowered or "usage limit" in lowered:
                limits = self.rate_limits()
                raise ProviderRateLimited(
                    "Your Codex allowance is temporarily exhausted.",
                    details={"rate_limits": limits},
                ) from exc
            if "unauthorized" in lowered or "authentication" in lowered:
                raise ProviderAuthenticationExpired(
                    "Codex authentication expired. Sign in again."
                ) from exc
            raise
        finally:
            self._active_turns.pop(conversation_id, None)

    def cancel_generation(self, conversation_id: int) -> None:
        active = self._active_turns.get(conversation_id)
        if not active:
            return
        thread_id, turn_id = active
        sdk = self._require_sdk()
        sdk._client.turn_interrupt(thread_id, turn_id)

    def generate_text(
        self,
        prompt: str,
        *,
        system_prompt: str = "",
        model: str | None = None,
    ) -> str:
        """One-shot text generation for background jobs (Smart Collections, etc.)."""
        self._ensure_chatgpt_account()
        sdk = self._require_sdk()
        client = getattr(sdk, "_client", None)
        if client is None:
            raise ProviderUnavailable("The installed Codex SDK does not expose a turn transport.")

        session_dir = Path(get_app_data_dir()) / "ai_sessions" / f"sc-{uuid4()}"
        session_dir.mkdir(parents=True, exist_ok=True)
        resolved_model = model or self.default_model()
        developer = (system_prompt or "").strip() or SMART_COLLECTION_INSTRUCTIONS
        try:
            thread = sdk.thread_start(
                approval_mode=ApprovalMode.deny_all,
                cwd=str(session_dir.resolve()),
                developer_instructions=developer,
                model=resolved_model,
                sandbox=Sandbox.read_only,
                service_name="research_marker",
            )
            turn_params: dict[str, Any] = {
                "cwd": str(session_dir.resolve()),
                "approvalPolicy": "never",
                "sandboxPolicy": READ_ONLY_SANDBOX_POLICY,
            }
            if resolved_model:
                turn_params["model"] = resolved_model
            started = client.turn_start(
                thread.id,
                [{"type": "text", "text": prompt}],
                params=turn_params,
            )
            turn_id = started.turn.id
            client.register_turn_notifications(turn_id)
            answer_parts: list[str] = []
            try:
                while True:
                    notification = client.next_turn_notification(turn_id)
                    if notification.method == "item/agentMessage/delta":
                        answer_parts.append(notification.payload.delta)
                    elif notification.method == "turn/completed":
                        status = str(notification.payload.turn.status.value)
                        if status == "interrupted":
                            raise GenerationCancelled("Codex generation was cancelled.")
                        if status == "failed":
                            error = notification.payload.turn.error
                            message = _codex_error_message(error) or "Codex generation failed."
                            if "rate" in message.lower() and "limit" in message.lower():
                                raise ProviderRateLimited(message)
                            raise ProviderUnavailable(message)
                        break
            finally:
                client.unregister_turn_notifications(turn_id)

            answer = "".join(answer_parts).strip()
            if not answer:
                raise ProviderUnavailable("Codex returned an empty response.")
            return answer
        except (GenerationCancelled, ProviderRateLimited, ProviderUnavailable):
            raise
        except Exception as exc:
            lowered = str(exc).lower()
            if "rate limit" in lowered or "usage limit" in lowered:
                raise ProviderRateLimited(
                    "Your Codex allowance is temporarily exhausted."
                ) from exc
            if "unauthorized" in lowered or "authentication" in lowered:
                raise ProviderAuthenticationExpired(
                    "Codex authentication expired. Sign in again."
                ) from exc
            raise ProviderUnavailable(f"Codex generation failed: {exc}") from exc
        finally:
            shutil.rmtree(session_dir, ignore_errors=True)

    def list_conversations(self) -> list[dict[str, Any]]:
        return [
            {
                "local_conversation_id": item.id,
                "codex_thread_id": item.codex_thread_id,
                "document_id": item.document_id,
                "title": item.name,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "updated_at": item.updated_at.isoformat(),
            }
            for item in models.ChatLogs.objects.filter(provider="codex").order_by("-updated_at")
        ]

    def cleanup_sessions(self) -> int:
        root = Path(get_app_data_dir()) / "ai_sessions"
        if not root.exists():
            return 0
        cutoff = datetime.now(timezone.utc) - timedelta(hours=SESSION_RETENTION_HOURS)
        removed = 0
        for directory in root.iterdir():
            if not directory.is_dir():
                continue
            modified = datetime.fromtimestamp(directory.stat().st_mtime, tz=timezone.utc)
            if modified < cutoff:
                shutil.rmtree(directory, ignore_errors=True)
                removed += 1
        return removed


_CODEX_PROVIDER = CodexProvider()


def get_codex_provider() -> CodexProvider:
    return _CODEX_PROVIDER
