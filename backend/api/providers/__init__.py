"""AI provider adapters.

Import-light package init so PyInstaller ``collect_submodules`` can discover
submodules without Django settings in its isolated scanner process.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "AIProvider",
    "APIKeyProviderAdapter",
    "CodexProvider",
    "EmbeddingProvider",
    "EmbeddingSpec",
    "build_embedding_provider",
    "embedding_provider_catalog",
    "get_codex_provider",
]


def __getattr__(name: str) -> Any:
    if name == "AIProvider":
        from .base import AIProvider

        return AIProvider
    if name in {"CodexProvider", "get_codex_provider"}:
        from .codex import CodexProvider, get_codex_provider

        return {"CodexProvider": CodexProvider, "get_codex_provider": get_codex_provider}[name]
    if name in {
        "EmbeddingProvider",
        "EmbeddingSpec",
        "build_embedding_provider",
        "embedding_provider_catalog",
    }:
        from .embeddings import (
            EmbeddingProvider,
            EmbeddingSpec,
            build_embedding_provider,
            embedding_provider_catalog,
        )

        return {
            "EmbeddingProvider": EmbeddingProvider,
            "EmbeddingSpec": EmbeddingSpec,
            "build_embedding_provider": build_embedding_provider,
            "embedding_provider_catalog": embedding_provider_catalog,
        }[name]
    if name == "APIKeyProviderAdapter":
        from .legacy import APIKeyProviderAdapter

        return APIKeyProviderAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
