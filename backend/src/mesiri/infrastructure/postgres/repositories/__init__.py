"""PostgreSQL repository implementations.

Lazy re-exports (PEP 562) so importing any one submodule under this package
(e.g. `.material_execution`) does not eagerly load every sibling's sqlalchemy
import — `projects.py` imports sqlalchemy at module level (unlike the lazy-
import convention every other adapter in this codebase follows), which was
tripping the platform/ shadow-package issue for any test merely importing a
sibling module. No caller actually uses this package-level re-export
(everyone imports the submodule directly); it's kept only for API stability.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "PostgresProjectRepository",
    "PostgresAIConfigRepository",
]


def __getattr__(name: str) -> Any:
    if name == "PostgresProjectRepository":
        from .projects import PostgresProjectRepository

        return PostgresProjectRepository
    if name == "PostgresAIConfigRepository":
        from .ai_config import PostgresAIConfigRepository

        return PostgresAIConfigRepository
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
