"""Deployable ASGI entrypoint for the API/health service (M1).

The application factory lives in the importable ``mesiri`` package. Run with:

    uvicorn --factory mesiri.http.app:create_app --host 0.0.0.0 --port 8000

(with ``backend/src`` on PYTHONPATH). This module simply re-exports the factory
so ``mesiri.apps.api.main`` style references also resolve.
"""

from mesiri.http.app import create_app

__all__ = ["create_app"]
