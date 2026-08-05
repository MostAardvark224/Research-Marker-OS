from __future__ import annotations

from dataclasses import dataclass

from api.ai import AI_PROVIDER_CONFIG, get_provider_api_key, normalize_provider
from api.errors import EmbeddingConfigurationError, ProviderNotAuthenticated
from api.providers.embeddings import (
    DEFAULT_EMBEDDING_DIMENSIONS,
    EMBEDDING_PROVIDER_CONFIG,
    EmbeddingSpec,
    normalize_embedding_provider,
)
from api.user_preferences import load_user_preferences
from api.utils import load_env_vars


@dataclass(frozen=True, slots=True)
class SmartCollectionConfig:
    embedding: EmbeddingSpec
    generation_provider: str
    generation_model: str


def _ai_preferences() -> dict:
    data = load_user_preferences()
    return data.get("user_preferences", {}).get("ai", {})


def get_smart_collection_config(
    *,
    embedding_provider: str | None = None,
    embedding_model: str | None = None,
    generation_provider: str | None = None,
    generation_model: str | None = None,
) -> SmartCollectionConfig:
    ai = _ai_preferences()
    settings = ai.get("smart_collections", {}) or {}
    embedding_models = settings.get("embedding_models", {}) or {}

    selected_embedding_provider = normalize_embedding_provider(
        embedding_provider or settings.get("embedding_provider") or "gemini"
    )
    embedding_config = EMBEDDING_PROVIDER_CONFIG[selected_embedding_provider]
    selected_embedding_model = str(
        embedding_model
        or embedding_models.get(selected_embedding_provider)
        or embedding_config["default_model"]
        or ""
    ).strip()
    if not selected_embedding_model:
        raise EmbeddingConfigurationError("Choose an embedding model.")

    selected_generation_provider = normalize_provider(
        generation_provider
        or settings.get("generation_provider")
        or ai.get("default_provider")
        or "gemini"
    )
    selected_generation_model = str(
        generation_model
        or settings.get("generation_model")
        or (ai.get("models", {}) or {}).get(selected_generation_provider)
        or AI_PROVIDER_CONFIG[selected_generation_provider]["default_chat_model"]
        or ""
    ).strip()
    if not selected_generation_model:
        raise ProviderNotAuthenticated("Choose a model for Smart Collection labels.")

    env = load_env_vars()
    if selected_embedding_provider == "custom":
        base_url = str(env.get("CUSTOM_AI_BASE_URL", "")).strip()
        if not base_url:
            raise EmbeddingConfigurationError(
                "Configure the Custom Server base URL before using local embeddings."
            )
    else:
        env_key = embedding_config["api_key_env"]
        if not env.get(env_key):
            raise EmbeddingConfigurationError(
                f"Add {env_key} in Settings before building a Smart Collection."
            )
        base_url = ""

    if selected_generation_provider == "codex":
        raise ProviderNotAuthenticated(
            "Codex is not available for background Smart Collection labeling. "
            "Choose Gemini, OpenAI, Claude, OpenRouter, or Custom Server."
        )
    if selected_generation_provider != "custom" and not get_provider_api_key(
        selected_generation_provider, env
    ):
        raise ProviderNotAuthenticated(
            f"Add the {AI_PROVIDER_CONFIG[selected_generation_provider]['label']} API key "
            "before building a Smart Collection."
        )
    if selected_generation_provider == "custom" and not env.get("CUSTOM_AI_BASE_URL"):
        raise ProviderNotAuthenticated(
            "Configure the Custom Server base URL before building a Smart Collection."
        )

    return SmartCollectionConfig(
        embedding=EmbeddingSpec(
            provider=selected_embedding_provider,
            model=selected_embedding_model,
            dimensions=DEFAULT_EMBEDDING_DIMENSIONS,
            base_url=base_url,
        ),
        generation_provider=selected_generation_provider,
        generation_model=selected_generation_model,
    )
