"""Constants shared by 2+ of this package's submodules.

Kept separate from any one submodule so neither has to import the other just
to reach a bare constant -- see the package's __init__.py for the re-export
surface these feed into.
"""

from __future__ import annotations

import logging

_log = logging.getLogger("mesiri.inbound_journey")
