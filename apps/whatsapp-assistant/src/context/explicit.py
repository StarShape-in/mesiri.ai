"""Explicit project/site reference extraction from UnderstandingResult (M4).

The understanding pipeline (M3) surfaces *semantic references* — a project name,
a site name, occasionally an identifier the user typed. This module reads those
references out of the extraction candidates. It never assigns an authoritative
id: the resolver maps a reference to an authorized record. If the LLM emits a
value in a ``*_id`` field it is treated as a *user-supplied* reference and still
validated against authorized records (never trusted as authoritative).
"""

from __future__ import annotations

from dataclasses import dataclass

from mesiri_contracts.assistant.understanding_result import UnderstandingResult

# Recognised keys inside a candidate's ``fields`` / ``unknown_fields``.
_PROJECT_ID_KEYS = ("project_id",)
_PROJECT_NAME_KEYS = ("project", "project_name", "project_reference", "site_project")
_SITE_ID_KEYS = ("site_id",)
_SITE_NAME_KEYS = ("site", "site_name", "site_reference", "block", "zone")


@dataclass(frozen=True, slots=True)
class ProjectRef:
    value: str
    by_id: bool


@dataclass(frozen=True, slots=True)
class SiteRef:
    value: str
    by_id: bool


def _first(fields: dict, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        val = fields.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return None


def extract_references(
    understanding: UnderstandingResult,
) -> tuple[ProjectRef | None, SiteRef | None]:
    """Return the first explicit (project, site) references found, if any.

    Prefers an id-shaped reference over a name for confidence, but both are
    validated against authorized records downstream.
    """
    project_ref: ProjectRef | None = None
    site_ref: SiteRef | None = None

    for candidate in understanding.candidates:
        merged = {**candidate.fields, **candidate.unknown_fields}

        if project_ref is None:
            pid = _first(merged, _PROJECT_ID_KEYS)
            if pid is not None:
                project_ref = ProjectRef(value=pid, by_id=True)
            else:
                pname = _first(merged, _PROJECT_NAME_KEYS)
                if pname is not None:
                    project_ref = ProjectRef(value=pname, by_id=False)

        if site_ref is None:
            sid = _first(merged, _SITE_ID_KEYS)
            if sid is not None:
                site_ref = SiteRef(value=sid, by_id=True)
            else:
                sname = _first(merged, _SITE_NAME_KEYS)
                if sname is not None:
                    site_ref = SiteRef(value=sname, by_id=False)

        if project_ref is not None and site_ref is not None:
            break

    return project_ref, site_ref
