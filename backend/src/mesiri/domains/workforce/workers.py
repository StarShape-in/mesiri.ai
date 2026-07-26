"""Workforce vocabulary — worker types, statuses, and trade normalization.

Pure domain: no I/O, no SQL, no framework. Mirrors the thin-domain shape
Material uses (domains/materials/validation.py) rather than Expense's richer
DDD layer, since Material is the canonical operational module.

Deliberately small. The workforce register is operational reference data —
who can be recorded as having worked — and nothing more. It is **not** an HR
record: no addresses, identity documents, bank details or next of kin. If
those are ever wanted they belong to an HR module with its own consent and
retention rules, not here.
"""

from __future__ import annotations

import re
from enum import Enum


class WorkerType(str, Enum):
    """How a worker is engaged.

    TEMPORARY is not a lesser case: on many sites, daily-hire labour is 30-60%
    of attendance. It is a first-class type supported everywhere PERMANENT is
    (see the Labour plan's principle P3), and specifically it does **not**
    imply "not yet in the register" — a temporary worker who returns often can
    live in the register with TEMPORARY as their type.
    """

    PERMANENT = "permanent"
    TEMPORARY = "temporary"
    CONTRACTOR = "contractor"


class WorkerStatus(str, Enum):
    """Whether this worker may be recorded on new attendance.

    Registered workers are never hard-deleted -- historical attendance
    references them, and attendance is immutable (principle P5). Retiring
    someone means INACTIVE.
    """

    ACTIVE = "active"
    INACTIVE = "inactive"


VALID_WORKER_TYPES: frozenset[str] = frozenset(t.value for t in WorkerType)
VALID_WORKER_STATUSES: frozenset[str] = frozenset(s.value for s in WorkerStatus)


def parse_worker_type(value: object) -> WorkerType | None:
    """Coerce free text to a WorkerType, or None if unrecognised.

    Tolerant of the casing and spacing that arrive from AI extraction and
    from API callers; never guesses between types.
    """
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not text:
        return None
    # "daily", "casual" and "daily_wage" are how site staff describe temporary
    # hire; accepting them here avoids pushing that vocabulary onto the caller.
    if text in ("temporary", "temp", "daily", "daily_wage", "casual"):
        return WorkerType.TEMPORARY
    if text in ("contractor", "contract", "subcontractor", "sub_contractor"):
        return WorkerType.CONTRACTOR
    if text in ("permanent", "regular", "staff", "full_time"):
        return WorkerType.PERMANENT
    return None


# Trades are deliberately NOT a closed enum. Construction trade vocabulary
# varies by region, language and company, and rejecting an unknown trade would
# block a report for no operational gain (principle P9 -- optimize for speed of
# recording). Instead trades are normalized free text, and this table only
# collapses the spellings we know collide.
_TRADE_SYNONYMS: dict[str, str] = {
    "mason": "mason",
    "masons": "mason",
    "mistri": "mason",
    "bricklayer": "mason",
    "helper": "helper",
    "helpers": "helper",
    "labour": "helper",
    "labourer": "helper",
    "labourers": "helper",
    "laborer": "helper",
    "coolie": "helper",
    "painter": "painter",
    "painters": "painter",
    "carpenter": "carpenter",
    "carpenters": "carpenter",
    "electrician": "electrician",
    "electricians": "electrician",
    "plumber": "plumber",
    "plumbers": "plumber",
    "welder": "welder",
    "welders": "welder",
    "bar_bender": "bar_bender",
    "barbender": "bar_bender",
    "steel_fixer": "bar_bender",
    "fitter": "fitter",
    "fitters": "fitter",
    "supervisor": "supervisor",
    "operator": "operator",
    "driver": "driver",
}


def normalize_trade(value: object) -> str | None:
    """Normalize a trade to a comparable form, or None if absent.

    Used both when storing and when matching, so "Masons", "mason" and
    "mistri" resolve to the same trade rather than looking like three
    different ones. An unrecognised trade is kept as-is (lowercased,
    underscored) rather than rejected -- see _TRADE_SYNONYMS' note.
    """
    text = str(value or "").strip().lower()
    if not text:
        return None
    text = re.sub(r"[\s\-]+", "_", text)
    text = re.sub(r"[^a-z0-9_]", "", text)
    if not text:
        return None
    return _TRADE_SYNONYMS.get(text, text)


def normalize_name(value: object) -> str:
    """Normalize a worker name for comparison only — never for display.

    Collapses case, punctuation and repeated whitespace so "Ravi  Kumar",
    "ravi kumar" and "Ravi-Kumar" compare equal. The original spelling is
    always what gets stored and shown back; this is strictly a matching aid.
    """
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()
