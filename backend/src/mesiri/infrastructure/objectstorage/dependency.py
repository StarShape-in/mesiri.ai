"""FastAPI dependency that yields the process's ObjectStoragePort.

Mirrors infrastructure/postgres/dependency.py's get_db_conn shape and
fallback order (lifecycle.container first, bare container second, build a
fresh adapter from settings as a last resort) so REST routes that need to
serve media (e.g. presigned receipt URLs) don't have to know how the
process was wired.
"""

from __future__ import annotations

from fastapi import Request

from mesiri_contracts.common.storage import ObjectStoragePort


def get_object_storage(request: Request) -> ObjectStoragePort:
    if hasattr(request.app.state, "lifecycle"):
        return request.app.state.lifecycle.container.object_storage
    if hasattr(request.app.state, "container"):
        return request.app.state.container.object_storage

    from mesiri.bootstrap.settings import get_settings
    from mesiri.infrastructure.objectstorage import build_object_storage

    return build_object_storage(get_settings())
