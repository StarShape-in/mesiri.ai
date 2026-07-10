"""Automated architecture-boundary checks (M3 / §37).

Static source scans that fail if a module reaches across a boundary it must not:
provider SDKs must stay inside adapters, and the understanding pipeline must not
touch persistence, provider SDKs, or business repositories (it produces
understanding, never business records).
"""

from __future__ import annotations

import pathlib

REPO = pathlib.Path(__file__).resolve().parents[3]
UNDERSTANDING = REPO / "apps" / "whatsapp-assistant" / "src" / "understanding"
MESIRI_AI = REPO / "platform" / "ai" / "src" / "mesiri_ai"

_PERSISTENCE_SDKS = (
    "import sqlalchemy",
    "import psycopg",
    "import asyncpg",
    "import boto3",
    "import redis",
)
_PROVIDER_SDKS = ("from google", "import google", "from sarvamai", "import sarvamai")
_BUSINESS_WRITES = ("expense_repository", "_repository.insert", "infrastructure.postgres")


def _sources(root: pathlib.Path) -> list[pathlib.Path]:
    return [p for p in root.rglob("*.py") if p.name != "__init__.py"]


def test_understanding_does_not_touch_persistence_or_sdks():
    for path in _sources(UNDERSTANDING):
        text = path.read_text(encoding="utf-8")
        for needle in _PERSISTENCE_SDKS + _PROVIDER_SDKS + _BUSINESS_WRITES:
            assert needle not in text, f"{path.name} must not reference {needle!r}"


def test_provider_sdks_only_imported_inside_adapters():
    for path in _sources(MESIRI_AI):
        is_adapter = "adapters" in path.parts
        if is_adapter:
            continue
        text = path.read_text(encoding="utf-8")
        for needle in _PROVIDER_SDKS:
            assert needle not in text, f"{path} imports provider SDK {needle!r} outside adapters/"


def test_ports_depend_only_on_models_not_sdks():
    for path in (MESIRI_AI / "ports").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "import boto3" not in text
        for needle in _PROVIDER_SDKS:
            assert needle not in text
