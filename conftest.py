"""Root conftest.py — monorepo-level pytest bootstrap.

The repo contains a top-level ``platform/`` directory (mesiri_ai lives at
``platform/ai/src``). When pytest prepends entries like ``platform/ai/src``
to sys.path, Python may resolve the parent ``platform/`` as a namespace
package that shadows the stdlib ``platform`` module.  SQLAlchemy does
``platform.python_implementation()`` at import time; if the namespace package
shadows it, collection fails with AttributeError.

FIX: pytest processes ``[tool.pytest.ini_options] pythonpath`` and then loads
this conftest.py.  By that time ``platform`` may already be in sys.modules as
the namespace package.  We bypass sys.path entirely: ``sysconfig.get_path``
gives us the concrete stdlib directory, and we load ``platform.py`` from it
directly with importlib, then force it into sys.modules before any test
module triggers the SQLAlchemy import chain.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import sys
import sysconfig

_stdlib_dir = sysconfig.get_path("stdlib")
_platform_py = os.path.join(_stdlib_dir, "platform.py")

if os.path.isfile(_platform_py):
    _loader = importlib.machinery.SourceFileLoader("platform", _platform_py)
    _spec = importlib.util.spec_from_loader("platform", _loader)
    _mod = importlib.util.module_from_spec(_spec)
    _loader.exec_module(_mod)
    # Force-override whatever is in sys.modules (namespace pkg or nothing).
    sys.modules["platform"] = _mod
