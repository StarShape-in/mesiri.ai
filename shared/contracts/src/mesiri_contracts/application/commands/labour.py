"""Labour Application Command — the typed handoff from ConfirmedActionV2.

Placed here rather than under the backend's application package because
Material — the canonical operational module — puts its commands here, and
where Material and Expense disagree the Labour plan says follow Material.

One command, not several: V1 has exactly one operational action (Record
Attendance). Direction/variant flags that Material needed (receipt vs usage)
have no analogue here.

Two shape decisions worth understanding before changing anything:

**1. A line is either a named person or a headcount group.**
Real sites report both ways, sometimes in the same message::

    Ravi - Mason
    Arun - Painter
    12 Helpers
    4 Carpenters

Forcing one style would push away whichever half of users doesn't work that
way, so a line carries an optional identity and an explicit `headcount`.
`headcount=1` with a name is one person; `headcount=12` with no name is a
group. The workflow never has to choose a mode, and one attendance can mix
both freely.

**2. Wage and trade are copied onto the line, not referenced.**
Attendance is immutable history (plan principle P5). If a line merely
pointed at the register, editing a worker's daily wage next month would
silently rewrite what last month's attendance appears to have cost. The
value actually used is therefore stored on the line at the moment of
recording.

`project_id` is nullable here even though persistence requires it, for the
same reason Material's is: an unresolved project is a routine outcome of
context resolution, and the mapper must never invent one — Domain validation
rejects it honestly instead.

Ownership: SHARED ARCHITECTURE — part of the M0 contract surface. Version: v2.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from mesiri_contracts.assistant.v2.uuid_scope import CanonicalUuid

CONTRACT_VERSION = "v2"


class LabourAttendanceLine(BaseModel):
    """One line of an attendance report.

    Either a named worker (``worker_name`` set, ``headcount`` 1) or an
    anonymous group of a trade (``worker_name`` unset, ``headcount`` > 1).
    Both forms coexist in the same attendance.
    """

    version: str = CONTRACT_VERSION

    #: Set only for a named individual. None for a headcount group.
    #: Always Latin script — a name written in Malayalam, Hindi or Tamil is
    #: transliterated (രവി -> "Ravi"), never translated, since a name is a
    #: person rather than vocabulary.
    worker_name: str | None = None

    #: The name exactly as written, when the source wasn't Latin script.
    #: Stored because transliteration is a judgement call with no single right
    #: answer ("Ravi"/"Ravy"), and losing the original would make a
    #: mis-transliteration permanently unverifiable against the paper sheet.
    #: None when the source was already Latin, so it adds nothing there.
    worker_name_original: str | None = None

    #: Set once matching has resolved this line to someone already in the
    #: workforce register. None means "not in the register" — either a
    #: genuinely new person or a headcount group. Crucially it does NOT mean
    #: "add them to the register": attendance never writes the register
    #: (principle P1). Promotion is a separate, explicit act.
    worker_id: CanonicalUuid | None = None

    #: Normalized trade (see domains/workforce/workers.normalize_trade).
    trade: str | None = None

    #: How many people this line represents. 1 for a named worker.
    headcount: int = 1

    #: The wage actually used for this line, copied from the register or
    #: stated in the report. Stored rather than referenced so historical cost
    #: cannot drift when the register is later edited.
    daily_wage: Decimal | None = None

    #: Free text in V1 by deliberate decision — site vocabulary is
    #: inconsistent ("Kumar Team", "ABC Contractors", "Local Labour") and
    #: normalizing it now would add complexity without operational gain.
    #: Converting free text into a Contractor entity later is straightforward;
    #: the reverse is not.
    contractor: str | None = None

    #: Optional activity / work item this line worked on. Carried even though
    #: V1 exposes no activity management, because the
    #: Materials -> Activity -> Labour -> Expenses link cannot be
    #: reconstructed after the fact (principle P7).
    activity: str | None = None

    #: P / A / H on a muster roll. "present" for everything a typed message
    #: reports, because a supervisor writing names only ever names people who
    #: worked. A photographed sheet lists the whole crew, absentees included --
    #: without this a sheet would invent a day's work and a day's wage for
    #: everyone who did not turn up.
    #:
    #: An absent line is still *recorded*: the sheet said so, and "nobody
    #: reported Ravi" and "Ravi was marked absent" are different facts. It
    #: simply contributes no man-days and no cost.
    attendance_status: str = "present"

    #: Overtime hours from the sheet's own OT column, kept separate from the
    #: day's wage rather than folded into it -- a wage that has silently
    #: absorbed overtime cannot be taken apart again. Nothing computes OT pay
    #: yet: the rate rules differ per contractor and are not being guessed at.
    overtime_hours: Decimal | None = None

    #: The free-text column at the edge of every sheet ("left early", "site
    #: closed 2pm"). Often the only explanation of why a day looks unusual.
    remarks: str | None = None

    #: Man-days this line actually contributes. Half a day is expressed here
    #: rather than by making `headcount` fractional -- headcount is a count of
    #: people, and 0.5 people is not a thing.
    @property
    def day_fraction(self) -> Decimal:
        if self.attendance_status == "absent":
            return Decimal("0")
        if self.attendance_status == "half_day":
            return Decimal("0.5")
        return Decimal("1")

    model_config = {"extra": "forbid"}

    @property
    def line_cost(self) -> Decimal:
        """Operational cost of this line. Not payroll — no overtime pay, no
        deductions, no statutory contributions (all explicitly out of scope).

        Scaled by the day fraction, so a half day costs half a day and an
        absent line costs nothing. Charging a full wage against a sheet that
        says "H" would be inventing money, which is the one thing this module
        must never do."""
        if self.daily_wage is None:
            return Decimal("0")
        return self.daily_wage * self.headcount * self.day_fraction


class RecordLabourAttendanceCommand(BaseModel):
    """Record who worked on a site on a given day."""

    version: str = CONTRACT_VERSION

    command_id: str
    idempotency_key: str
    correlation_id: str

    organization_id: CanonicalUuid
    project_id: CanonicalUuid | None
    site_id: CanonicalUuid | None

    lines: list[LabourAttendanceLine]

    notes: str | None = None

    #: Object-storage keys for attendance sheet photos, attached through the
    #: same mechanism receipts use (plan ADR-L3) so Timeline and Image Gallery
    #: consume them without Labour building anything image-specific.
    attachment_object_keys: list[str] = []

    occurred_date: date
    occurred_date_source: str = "inferred_at_confirmation"

    #: How this report reached Mesiri: "whatsapp_text" | "whatsapp_voice" |
    #: "whatsapp_image" | "dashboard". Simple provenance metadata — it plays
    #: no part in matching, validation or the domain rules above — but
    #: valuable later for debugging AI accuracy per input path and for
    #: analytics, and it cannot be reconstructed once the report is saved.
    #: Set from the real input modality at canonicalization
    #: (canonicalization/builder.py, from UnderstandingResult.input_modality)
    #: for the message that started the workflow; slot-filling replies later
    #: in the same conversation never overwrite it.
    recorded_via: str = "whatsapp_text"

    #: Set when this report replaces an earlier one for the same site and day,
    #: because the supervisor re-sent the list rather than editing it (which
    #: attendance does not allow -- principle P5). Both rows survive: the
    #: superseded one stays fully readable for audit, but stops feeding any
    #: total, which is what keeps a re-sent day of 18 workers from reading as
    #: 16 + 18 = 34 man-days.
    #:
    #: None means "this is a genuinely separate report" -- a second shift, or a
    #: different crew on the same site and day -- and both then count. The
    #: choice is the supervisor's, asked before anything is written; nothing
    #: here infers it.
    corrects_report_id: CanonicalUuid | None = None

    created_by: CanonicalUuid

    model_config = {"extra": "forbid"}

    @property
    def total_headcount(self) -> int:
        """People actually present. An absent line is recorded but is not a
        person who worked, so it must not appear in a headcount a supervisor
        is asked to confirm -- a sheet of 20 with 3 absent is 17 workers."""
        return sum(line.headcount for line in self.lines if line.attendance_status != "absent")

    @property
    def total_cost(self) -> Decimal:
        return sum((line.line_cost for line in self.lines), Decimal("0"))
