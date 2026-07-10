"""Application queries for projects domain.

Queries are read-only operations that fetch data without side effects.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ListProjects:
    """Query to list all projects accessible to the current user.

    This is a marker query with no parameters. The authorization context
    (provided by the handler) determines which projects are accessible.
    """

    pass
