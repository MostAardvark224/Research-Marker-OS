from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from api.ai import send_prompt
from api.paper_context.builder import PAPER_ANSWER_INSTRUCTIONS, format_paper_context
from api.paper_context.types import PaperContext
from .base import AIProvider


class APIKeyProviderAdapter(AIProvider):
    """Adapts existing API-key providers to consume PaperContext."""

    def __init__(self, provider: str, api_key: str, model: str, *, base_url: str = ""):
        self.provider = provider
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    def connect(self) -> dict[str, Any]:
        return self.get_status()

    def disconnect(self) -> None:
        return None

    def get_status(self) -> dict[str, Any]:
        return {"state": "connected" if self.api_key or self.provider == "custom" else "not_connected"}

    def create_conversation(self, document_id: int, title: str = "") -> Any:
        return None

    def send_message(
        self,
        conversation_id: int,
        question: str,
        paper_context: PaperContext,
    ) -> Iterator[dict[str, Any]]:
        response = send_prompt(
            provider=self.provider,
            api_key=self.api_key,
            model=self.model,
            prompt=format_paper_context(paper_context),
            chat_id=conversation_id,
            system_prompt=PAPER_ANSWER_INSTRUCTIONS,
            base_url=self.base_url,
        )
        yield {"type": "delta", "text": response}
        yield {"type": "completed"}

    def cancel_generation(self, conversation_id: int) -> None:
        return None

    def list_conversations(self) -> list[dict[str, Any]]:
        return []

    def resume_conversation(self, conversation_id: int) -> Any:
        return None
