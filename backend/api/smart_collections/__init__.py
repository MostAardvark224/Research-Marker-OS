"""Smart Collections package.

Keep this module import-light so PyInstaller's isolated ``collect_submodules``
can discover ``tasks`` / ``service`` / ``config`` without Django being set up.
Heavy symbols are exported lazily for callers that use ``api.smart_collections``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .config import (
        SmartCollectionConfig,
        get_smart_collection_config,
        resolve_embedding_spec,
    )
    from .service import build_smart_collection, serialize_job

__all__ = [
    "SmartCollectionConfig",
    "build_smart_collection",
    "get_smart_collection_config",
    "resolve_embedding_spec",
    "serialize_job",
]


def __getattr__(name: str) -> Any:
    if name in {"SmartCollectionConfig", "get_smart_collection_config", "resolve_embedding_spec"}:
        from .config import (
            SmartCollectionConfig,
            get_smart_collection_config,
            resolve_embedding_spec,
        )

        exports = {
            "SmartCollectionConfig": SmartCollectionConfig,
            "get_smart_collection_config": get_smart_collection_config,
            "resolve_embedding_spec": resolve_embedding_spec,
        }
        return exports[name]
    if name in {"build_smart_collection", "serialize_job"}:
        from .service import build_smart_collection, serialize_job

        exports = {
            "build_smart_collection": build_smart_collection,
            "serialize_job": serialize_job,
        }
        return exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
