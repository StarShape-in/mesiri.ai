"""Measure how well the AI reads real attendance sheet photos.

This exists because Labour's highest-risk assumption is a single question:
**can Gemini transcribe a handwritten muster roll well enough to trust?**
Every other part of the module -- worker matching, temporary workers, the
confirmation preview -- is built on top of that and is worthless if it fails.
Guessing the answer is not good enough, and neither is trying one tidy sample.

Run it against a folder of REAL photos: bad handwriting, bad light, creased
paper, glare, a phone held at an angle. Ideal scans prove nothing about a
supervisor standing in the sun.

    export MESIRI_GEMINI__API_KEY=...
    python scripts/eval_attendance_photos.py samples/attendance

The folder needs the images plus one `expected.json` giving ground truth:

    {
      "sheet_01.jpg": {
        "note": "biro on ruled paper, good light",
        "workers": [
          {"name": "Ravi Kumar", "trade": "mason",  "headcount": 1},
          {"name": "Arun",       "trade": "painter", "headcount": 1},
          {"name": null,         "trade": "helper",  "headcount": 12}
        ]
      }
    }

`name: null` means an unnamed group row. Transcribe ground truth by hand, from
the photo, exactly as written -- if you copy the model's own output you are
measuring nothing.

What it reports, and why each matters:

  name recall      -- of the people really on the sheet, how many were found.
                      Missing a worker means someone goes unpaid; this is the
                      number that decides whether the feature is usable.
  name precision   -- of the names returned, how many were really there.
                      Invented names are worse than missing ones: they enter
                      the register and corrupt matching for every later report.
  trade accuracy   -- on correctly-read names only, since a trade on a name
                      that was never there is meaningless.
  headcount error  -- total people, signed. Consistent under-counting on group
                      rows is a different fix from misreading handwriting.
  row-type errors  -- named person read as a group or vice versa. This one is
                      cheap to miss and expensive: it silently drops names.

Names are compared case- and punctuation-insensitively, because "ravi kumar"
and "Ravi Kumar" are the same worker; anything stricter would measure
formatting rather than reading. Nothing here writes to a database, and no
Mesiri account or tenant is touched -- it is the AI path only.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
for src in ("platform/ai/src", "shared/contracts/src", "backend/src", "apps/whatsapp-assistant/src"):
    sys.path.insert(0, str(REPO_ROOT / src))

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".heic"}


def _norm(name: object) -> str:
    """Compare names the way a person would: case and punctuation don't make
    it a different worker."""
    text = str(name or "").strip().lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _named(rows: list[dict]) -> list[str]:
    return [_norm(r.get("name")) for r in rows if _norm(r.get("name")) and _norm(r.get("name")) != "?"]


def _headcount(rows: list[dict]) -> int:
    total = 0
    for row in rows:
        try:
            total += int(float(str(row.get("headcount", 1))))
        except (TypeError, ValueError):
            total += 1
    return total


def _trade_of(rows: list[dict], name: str) -> str:
    for row in rows:
        if _norm(row.get("name")) == name:
            return _norm(row.get("trade"))
    return ""


def _group_rows(rows: list[dict]) -> int:
    return sum(1 for r in rows if not _norm(r.get("name")))


async def _read_sheet(path: Path) -> tuple[list[dict], str]:
    """Run the real vision call, then the real canonicalization, so this
    measures the pipeline the user actually hits -- not a hand-rolled prompt
    that happens to work."""
    from canonicalization.builder import _normalize_labour_fields
    from mesiri.bootstrap.settings import GeminiSettings
    from mesiri_ai.adapters.gemini.adapter import GeminiAdapter

    adapter = GeminiAdapter(GeminiSettings())
    vision = await adapter.analyze_image(
        path.read_bytes(),
        mime_type="image/jpeg",
        hint="labour_update",
        correlation_id=f"eval-{path.stem}",
    )
    fields: dict[str, Any] = dict(vision.raw_fields or {})
    normalized = _normalize_labour_fields(fields)
    rows = normalized.get("lines") or []
    # Report back in the ground-truth vocabulary ("name"), not the internal one.
    return (
        [
            {"name": r.get("worker_name"), "trade": r.get("trade"), "headcount": r.get("headcount", 1)}
            for r in rows
        ],
        vision.document_classification or "?",
    )


async def main(folder: str) -> int:
    directory = Path(folder)
    expected_path = directory / "expected.json"
    if not expected_path.exists():
        print(f"No ground truth at {expected_path}. See this file's docstring for the format.")
        return 2
    if not os.environ.get("MESIRI_GEMINI__API_KEY"):
        print("MESIRI_GEMINI__API_KEY is not set -- this script makes real, billed API calls.")
        return 2

    expected: dict[str, Any] = json.loads(expected_path.read_text(encoding="utf-8"))
    images = sorted(p for p in directory.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
    if not images:
        print(f"No images in {directory}.")
        return 2

    found_total = missed_total = invented_total = 0
    trade_right = trade_seen = 0
    head_delta_total = abs_head_error = 0
    rowtype_errors = 0
    failures: list[str] = []

    for image in images:
        truth = expected.get(image.name)
        if truth is None:
            print(f"  {image.name}: SKIPPED (no ground truth entry)")
            continue
        truth_rows = truth.get("workers", [])
        try:
            got_rows, classification = await _read_sheet(image)
        except Exception as exc:  # noqa: BLE001 -- an eval must report, not abort
            failures.append(f"{image.name}: {type(exc).__name__}: {exc}")
            print(f"  {image.name}: ERROR {type(exc).__name__}: {exc}")
            continue

        want, got = set(_named(truth_rows)), set(_named(got_rows))
        found, missed, invented = want & got, want - got, got - want
        found_total += len(found)
        missed_total += len(missed)
        invented_total += len(invented)

        for name in found:
            trade_seen += 1
            if _trade_of(truth_rows, name) == _trade_of(got_rows, name):
                trade_right += 1

        delta = _headcount(got_rows) - _headcount(truth_rows)
        head_delta_total += delta
        abs_head_error += abs(delta)
        rowtype_delta = abs(_group_rows(got_rows) - _group_rows(truth_rows))
        rowtype_errors += rowtype_delta

        note = truth.get("note", "")
        print(f"\n  {image.name}  [{classification}]  {note}")
        print(f"    names   {len(found)}/{len(want)} found", end="")
        if missed:
            print(f", MISSED {sorted(missed)}", end="")
        if invented:
            print(f", INVENTED {sorted(invented)}", end="")
        print()
        print(f"    people  expected {_headcount(truth_rows)}, got {_headcount(got_rows)} ({delta:+d})")
        if rowtype_delta:
            print(f"    ROW TYPE  {rowtype_delta} named/group row(s) confused")

    want_total = found_total + missed_total
    got_total = found_total + invented_total
    print("\n" + "=" * 60)
    print(f"  sheets            {len(images)}")
    if want_total:
        print(f"  name recall       {found_total / want_total:.0%}  ({found_total}/{want_total})")
    if got_total:
        print(f"  name precision    {found_total / got_total:.0%}  ({found_total}/{got_total})")
    if trade_seen:
        print(f"  trade accuracy    {trade_right / trade_seen:.0%}  ({trade_right}/{trade_seen})")
    print(f"  headcount error   {head_delta_total:+d} total, {abs_head_error} absolute")
    print(f"  row-type errors   {rowtype_errors}")
    if failures:
        print(f"  hard failures     {len(failures)}")
        for line in failures:
            print(f"    {line}")
    print("=" * 60)
    print("Record the numbers and the failure modes in")
    print("docs/plans/labour-attendance-photo-eval.md before changing any prompt,")
    print("so the next run can be compared against this one.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(asyncio.run(main(sys.argv[1])))
