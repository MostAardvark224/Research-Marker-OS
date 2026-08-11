from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import logging
from typing import Any, cast

import numpy as np
import requests
from google import genai
from google.genai import types
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from api.errors import (
    EmbeddingAuthenticationError,
    EmbeddingConfigurationError,
    EmbeddingProviderUnavailable,
    EmbeddingRateLimited,
    EmbeddingResponseError,
)
from api.utils import load_env_vars


LOGGER = logging.getLogger(__name__)
DEFAULT_EMBEDDING_DIMENSIONS = 512
EMBEDDING_PIPELINE_VERSION = 2
EMBEDDING_REQUEST_TIMEOUT_SECONDS = 60


@dataclass(frozen=True, slots=True)
class EmbeddingSpec:
    provider: str
    model: str
    dimensions: int = DEFAULT_EMBEDDING_DIMENSIONS
    base_url: str = ""

    @property
    def identity(self) -> tuple[str, str, int, int]:
        return (
            self.provider,
            self.model,
            self.dimensions,
            EMBEDDING_PIPELINE_VERSION,
        )


EMBEDDING_PROVIDER_CONFIG: dict[str, dict[str, Any]] = {
    "gemini": {
        "label": "Gemini",
        "api_key_env": "GEMINI_API_KEY",
        "default_model": "gemini-embedding-2",
        "models": ["gemini-embedding-2", "gemini-embedding-001"],
        "batch_size": 50,
    },
    "openai": {
        "label": "OpenAI",
        "api_key_env": "OPENAI_API_KEY",
        "default_model": "text-embedding-3-small",
        "models": ["text-embedding-3-small", "text-embedding-3-large"],
        "batch_size": 100,
    },
    "custom": {
        "label": "Custom OpenAI-compatible",
        "api_key_env": "CUSTOM_AI_API_KEY",
        "base_url_env": "CUSTOM_AI_BASE_URL",
        "default_model": "",
        "models": [],
        "batch_size": 50,
    },
}


class _TransientEmbeddingError(Exception):
    pass


def normalize_embedding_provider(provider: str | None) -> str:
    normalized = str(provider or "gemini").strip().lower()
    aliases = {
        "google": "gemini",
        "local": "custom",
        "openai-compatible": "custom",
        "openai_compatible": "custom",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in EMBEDDING_PROVIDER_CONFIG:
        raise EmbeddingConfigurationError(
            f"Unsupported embedding provider: {normalized or '(empty)'}."
        )
    return normalized


def normalize_openai_base_url(value: str) -> str:
    url = str(value or "").strip().rstrip("/")
    if not url:
        return ""
    if url.endswith("/embeddings"):
        url = url[: -len("/embeddings")].rstrip("/")
    if not url.endswith("/v1"):
        url = f"{url}/v1"
    return url


def embedding_provider_catalog(env_vars: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    env = env_vars if env_vars is not None else load_env_vars()
    catalog = []
    for provider_id, config in EMBEDDING_PROVIDER_CONFIG.items():
        base_url = (
            normalize_openai_base_url(env.get(config.get("base_url_env", ""), ""))
            if config.get("base_url_env")
            else ""
        )
        configured = bool(base_url) if provider_id == "custom" else bool(
            env.get(config["api_key_env"], "")
        )
        catalog.append(
            {
                "id": provider_id,
                "label": config["label"],
                "models": list(config["models"]),
                "default_model": config["default_model"],
                "default_dimensions": DEFAULT_EMBEDDING_DIMENSIONS,
                "configured": configured,
                "base_url": base_url if provider_id == "custom" else None,
            }
        )
    return catalog


class EmbeddingProvider(ABC):
    def __init__(self, spec: EmbeddingSpec, *, batch_size: int) -> None:
        if spec.dimensions < 1:
            raise EmbeddingConfigurationError("Embedding dimensions must be positive.")
        self.spec = spec
        self.batch_size = max(1, batch_size)

    def embed_texts(self, texts: list[str]) -> list[np.ndarray]:
        if not texts:
            return []
        vectors: list[np.ndarray] = []
        for start in range(0, len(texts), self.batch_size):
            batch = [str(text) for text in texts[start : start + self.batch_size]]
            raw = self._with_retry(batch)
            vectors.extend(self._validate(raw, expected_count=len(batch)))
        return vectors

    def _with_retry(self, texts: list[str]) -> list[list[float]]:
        retryer = Retrying(
            retry=retry_if_exception_type(_TransientEmbeddingError),
            wait=wait_random_exponential(multiplier=1, max=20),
            stop=stop_after_attempt(4),
            reraise=True,
        )
        try:
            return retryer(self._embed_batch, texts)
        except _TransientEmbeddingError as exc:
            raise EmbeddingProviderUnavailable(
                f"{self.spec.provider.title()} embeddings are temporarily unavailable. Try again.",
                details={"provider": self.spec.provider, "model": self.spec.model},
            ) from exc

    def _validate(
        self, vectors: list[list[float]], *, expected_count: int
    ) -> list[np.ndarray]:
        if len(vectors) != expected_count:
            raise EmbeddingResponseError(
                "The embedding provider returned an unexpected number of vectors.",
                details={"expected": expected_count, "received": len(vectors)},
            )
        validated: list[np.ndarray] = []
        for values in vectors:
            vector = np.asarray(values, dtype=np.float32)
            if vector.ndim != 1 or vector.shape[0] != self.spec.dimensions:
                raise EmbeddingResponseError(
                    "The embedding provider returned an incompatible vector size.",
                    details={
                        "expected_dimensions": self.spec.dimensions,
                        "received_dimensions": int(vector.shape[0]) if vector.ndim == 1 else None,
                    },
                )
            if not np.isfinite(vector).all():
                raise EmbeddingResponseError(
                    "The embedding provider returned non-finite vector values."
                )
            norm = float(np.linalg.norm(vector))
            if norm <= 0:
                raise EmbeddingResponseError("The embedding provider returned a zero vector.")
            validated.append((vector / norm).astype(np.float32, copy=False))
        return validated

    @abstractmethod
    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class GeminiEmbeddingProvider(EmbeddingProvider):
    def __init__(self, spec: EmbeddingSpec, *, api_key: str, batch_size: int) -> None:
        if not api_key:
            raise EmbeddingConfigurationError(
                "Add a Gemini API key in Settings before using Gemini embeddings."
            )
        super().__init__(spec, batch_size=batch_size)
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=EMBEDDING_REQUEST_TIMEOUT_SECONDS * 1000
            ),
        )

    @staticmethod
    def _as_contents(texts: list[str]) -> list[types.Content]:
        # gemini-embedding-2 runs list[str] through t_contents(), which merges
        # every string into one multi-part Content and returns a single vector.
        # Pass one Content per text so batch embedding stays 1:1.
        return [
            types.Content(
                role="user",
                parts=[types.Part(text=text if text.strip() else "(empty)")],
            )
            for text in texts
        ]

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        try:
            response = self._client.models.embed_content(
                model=self.spec.model,
                contents=cast(Any, self._as_contents(texts)),
                config=types.EmbedContentConfig(
                    output_dimensionality=self.spec.dimensions
                ),
            )
            return [list(item.values or []) for item in (response.embeddings or [])]
        except Exception as exc:
            message = str(exc)
            lowered = message.lower()
            if "429" in lowered or "resource_exhausted" in lowered or "quota" in lowered:
                raise EmbeddingRateLimited(
                    "Gemini embedding quota is exhausted. Try again later or select OpenAI embeddings.",
                    details={"provider": "gemini", "model": self.spec.model},
                ) from exc
            if "401" in lowered or "403" in lowered or "api key" in lowered:
                raise EmbeddingAuthenticationError(
                    "Gemini rejected the configured API key."
                ) from exc
            if any(token in lowered for token in ("timeout", "503", "502", "500", "unavailable")):
                raise _TransientEmbeddingError(message) from exc
            raise EmbeddingProviderUnavailable(
                f"Gemini embedding request failed: {message}"
            ) from exc


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        spec: EmbeddingSpec,
        *,
        api_key: str,
        batch_size: int,
        send_dimensions: bool = True,
    ) -> None:
        if spec.provider == "openai" and not api_key:
            raise EmbeddingConfigurationError(
                "Add an OpenAI API key in Settings before using OpenAI embeddings."
            )
        if not spec.base_url:
            raise EmbeddingConfigurationError(
                "Configure a custom OpenAI-compatible base URL before using local embeddings."
            )
        if not spec.model:
            raise EmbeddingConfigurationError("Choose an embedding model.")
        super().__init__(spec, batch_size=batch_size)
        self.api_key = api_key
        self.send_dimensions = send_dimensions

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        payload: dict[str, Any] = {"model": self.spec.model, "input": texts}
        if self.send_dimensions:
            payload["dimensions"] = self.spec.dimensions
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            response = requests.post(
                f"{self.spec.base_url}/embeddings",
                headers=headers,
                json=payload,
                timeout=(10, EMBEDDING_REQUEST_TIMEOUT_SECONDS),
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            raise _TransientEmbeddingError(str(exc)) from exc

        if response.status_code == 429:
            raise EmbeddingRateLimited(
                f"{self.spec.provider.title()} embedding quota is exhausted. Try again later.",
                details={"provider": self.spec.provider, "model": self.spec.model},
            )
        if response.status_code in (401, 403):
            raise EmbeddingAuthenticationError(
                f"{self.spec.provider.title()} rejected the configured API key."
            )
        if response.status_code >= 500:
            raise _TransientEmbeddingError(
                f"Embedding endpoint returned HTTP {response.status_code}."
            )
        try:
            response.raise_for_status()
            data = response.json().get("data", [])
            ordered = sorted(data, key=lambda item: int(item.get("index", 0)))
            return [item.get("embedding", []) for item in ordered]
        except (requests.HTTPError, ValueError, TypeError, KeyError) as exc:
            detail = ""
            try:
                detail = response.json().get("error", {}).get("message", "")
            except Exception:
                detail = response.text[:300]
            raise EmbeddingProviderUnavailable(
                f"{self.spec.provider.title()} embedding request failed"
                + (f": {detail}" if detail else ".")
            ) from exc


def build_embedding_provider(
    spec: EmbeddingSpec, *, env_vars: dict[str, Any] | None = None
) -> EmbeddingProvider:
    env = env_vars if env_vars is not None else load_env_vars()
    provider = normalize_embedding_provider(spec.provider)
    config = EMBEDDING_PROVIDER_CONFIG[provider]
    normalized_spec = EmbeddingSpec(
        provider=provider,
        model=spec.model or config["default_model"],
        dimensions=spec.dimensions,
        base_url=(
            "https://api.openai.com/v1"
            if provider == "openai"
            else normalize_openai_base_url(
                spec.base_url or env.get(config.get("base_url_env", ""), "")
            )
        ),
    )
    if provider == "gemini":
        return GeminiEmbeddingProvider(
            normalized_spec,
            api_key=env.get(config["api_key_env"], ""),
            batch_size=config["batch_size"],
        )
    return OpenAICompatibleEmbeddingProvider(
        normalized_spec,
        api_key=env.get(config["api_key_env"], ""),
        batch_size=config["batch_size"],
        send_dimensions=True,
    )
