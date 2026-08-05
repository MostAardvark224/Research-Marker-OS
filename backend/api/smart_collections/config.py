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


# Prefer Google's rolling aliases so Smart Collections keep working as pinned
# flash IDs age out of the generate API.
_LEGACY_GEMINI_GENERATION_MODELS = {
    "gemini-2.5-flash": "gemini-flash-latest",
    "gemini-2.5-flash-lite": "gemini-flash-lite-latest",
    "gemini-2.0-flash": "gemini-flash-latest",
    "gemini-2.0-flash-001": "gemini-flash-latest",
}


@dataclass(frozen=True, slots=True)
class SmartCollectionConfig:
    embedding: EmbeddingSpec
    generation_provider: str
    generation_model: str


def _ai_preferences() -> dict:
    data = load_user_preferences()
    return data.get("user_preferences", {}).get("ai", {})


def _default_generation_model(provider: str, ai: dict) -> str:
    saved = str((ai.get("models", {}) or {}).get(provider) or "").strip()
    if saved:
        return saved
    if provider == "codex":
        from api.providers.codex import get_codex_provider

        return str(get_codex_provider().default_model() or "").strip()
    return str(AI_PROVIDER_CONFIG[provider]["default_chat_model"] or "").strip()


def resolve_embedding_spec(
    *,
    embedding_provider: str | None = None,
    embedding_model: str | None = None,
) -> EmbeddingSpec:
    """Resolve embedding settings only — safe for the startup embed worker."""
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
                f"Add {env_key} in Settings before embedding annotations."
            )
        base_url = ""

    return EmbeddingSpec(
        provider=selected_embedding_provider,
        model=selected_embedding_model,
        dimensions=DEFAULT_EMBEDDING_DIMENSIONS,
        base_url=base_url,
    )


def get_smart_collection_config(
    *,
    embedding_provider: str | None = None,
    embedding_model: str | None = None,
    generation_provider: str | None = None,
    generation_model: str | None = None,
    require_generation: bool = True,
) -> SmartCollectionConfig:
    ai = _ai_preferences()
    settings = ai.get("smart_collections", {}) or {}
    embedding = resolve_embedding_spec(
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
    )

    selected_generation_provider = normalize_provider(
        generation_provider
        or settings.get("generation_provider")
        or ai.get("default_provider")
        or "gemini"
    )
    if selected_generation_provider != "codex" and selected_generation_provider not in AI_PROVIDER_CONFIG:
        selected_generation_provider = "gemini"

    selected_generation_model = str(
        generation_model
        or settings.get("generation_model")
        or _default_generation_model(selected_generation_provider, ai)
        or ""
    ).strip()
    if selected_generation_provider == "gemini":
        selected_generation_model = _LEGACY_GEMINI_GENERATION_MODELS.get(
            selected_generation_model,
            selected_generation_model,
        )

    if require_generation:
        if not selected_generation_model:
            raise ProviderNotAuthenticated("Choose a model for Smart Collection labels.")

        env = load_env_vars()
        if selected_generation_provider == "codex":
            from api.providers.codex import get_codex_provider

            status = get_codex_provider().get_status()
            if not status.get("subscription_usable"):
                raise ProviderNotAuthenticated(
                    "Connect Codex with your ChatGPT subscription in Settings before "
                    "using it for Smart Collection labels."
                )
        elif selected_generation_provider != "custom" and not get_provider_api_key(
            selected_generation_provider, env
        ):
            raise ProviderNotAuthenticated(
                f"Add the {AI_PROVIDER_CONFIG[selected_generation_provider]['label']} API key "
                "before building a Smart Collection."
            )
        elif selected_generation_provider == "custom" and not env.get("CUSTOM_AI_BASE_URL"):
            raise ProviderNotAuthenticated(
                "Configure the Custom Server base URL before building a Smart Collection."
            )

    return SmartCollectionConfig(
        embedding=embedding,
        generation_provider=selected_generation_provider,
        generation_model=selected_generation_model,
    )
