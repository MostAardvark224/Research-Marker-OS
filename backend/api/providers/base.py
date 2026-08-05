from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any

from api.paper_context.types import PaperContext


class AIProvider(ABC):
    @abstractmethod
    def connect(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_status(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def create_conversation(self, document_id: int, title: str = "") -> Any:
        raise NotImplementedError

    @abstractmethod
    def send_message(
        self,
        conversation_id: int,
        question: str,
        paper_context: PaperContext,
    ) -> Iterator[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def cancel_generation(self, conversation_id: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_conversations(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def resume_conversation(self, conversation_id: int) -> Any:
        raise NotImplementedError
