# Can the AI read a real attendance sheet?

**Status:** Harness ready and pipeline defects fixed. **Awaiting real photos —
the measurement has not been run.**
**Owner:** Alan Raj
**Created:** 2026-07-26
**Relates to:** `labour-module-implementation-plan.md` open question Q1

> This is the Labour module's highest-risk assumption. Worker matching,
> temporary workers, the confirmation preview — all of it sits on top of the
> AI being able to read a handwritten muster roll. If it can't, that is worth
> knowing before another week goes into persistence and dashboards.

---

## 1. Why this could not simply be tested

No real attendance sheet photographs exist in this repository, and none were
available to the session that built this harness. Neither were Gemini
credentials (`MESIRI_GEMINI__API_KEY` is unset locally, and provider-marked
tests are excluded from CI by design).

**No accuracy figure has therefore been produced, and none should be quoted
until §4 is filled in from a real run.** A number invented from synthetic or
idealised samples would be worse than no number: it would retire the risk on
paper while leaving it entirely in place.

What *was* possible without photos was auditing the path a photo travels, and
that turned out to matter more than expected — see §2.

## 2. Three defects found by reading the path, before any photo

All three were on the image route specifically. Every one of them would have
presented as *"the AI can't read handwriting"*, which is the expensive
misdiagnosis: it points at prompt tuning when the names were being read
correctly and discarded in transit.

### 2.1 The vision model was never told attendance sheets exist

`_VISION_PROMPT` offered `receipt, invoice, site_photo, unknown`. A muster
roll is none of those, so it would most likely classify as `unknown` — and
`understanding/pipeline.py` treats `unknown` plus empty fields as
**unreadable**, replying "image not interpretable". A perfectly legible sheet
could be rejected before extraction ran at all.

**Fixed:** `attendance_sheet` is now a classification, and the prompt
instructs the model to transcribe every row of a roster in order, with the
same `workers` schema the text path uses. It is told explicitly not to
summarise, not to total, and to emit `"?"` for an unreadable name rather than
drop the row — because a dropped row silently changes the headcount, while a
`"?"` is visible in the confirmation and can be corrected.

### 2.2 The vision prompt asked for flat key/values

`"fields" (object of any legible key/values)` suits a receipt's six scalars.
A roster is fifteen rows of two or three fields. There was no shape for the
model to put that in, so it would have invented one per photo.

**Fixed:** attendance sheets now have a declared `workers` array, identical in
vocabulary to the text extraction prompt, so both input paths converge on one
shape.

### 2.3 Structure was destroyed in the hand-off to extraction

The image path is vision → *text* → extraction. Vision's fields were flattened
with `"; ".join(f"{k}: {v}")`, which renders a list of dicts through Python's
`repr`:

```
Handwritten attendance register (workers: [{'name': 'Ravi', 'trade': 'mason'}])
```

Single quotes, not JSON. The extraction model then had to re-parse that by
eye. With fifteen workers it becomes an unparseable blob.

**Fixed:** lists and dicts are JSON-encoded; scalars still render as plain
prose, so the receipt path is byte-for-byte unchanged (pinned by
`test_a_receipt_read_is_unchanged_by_all_of_this`).

### 2.4 Bonus: the user's own answer was being ignored

`VisionUnderstandingProvider.analyze_image` has always accepted a `hint`. The
Gemini adapter ignored it and the pipeline never passed one. So when a
supervisor taps **Attendance** in the photo-purpose picker — telling us
exactly what the image is — the vision model was still left to guess.

**Fixed:** the tap is now passed through. On a creased, badly-lit sheet this
is likely the single highest-value change here, and it costs nothing.

## 3. How to run the measurement

```bash
export MESIRI_GEMINI__API_KEY=...
python scripts/eval_attendance_photos.py samples/attendance
```

The folder holds the photos plus an `expected.json` of hand-transcribed ground
truth (format in the script's docstring). **Transcribe ground truth from the
photo by hand.** Copying the model's own output measures nothing.

### What to photograph

Ideal scans prove nothing about a supervisor standing in the sun. Aim for
10–15 sheets spanning:

| Vary | Because |
|---|---|
| Handwriting — neat, rushed, mixed scripts | The core question |
| Light — sun glare, shade, indoor, evening | The most common real defect |
| Angle — flat, tilted, partly folded, creased | Phones are held one-handed |
| Layout — ruled columns, plain paper, printed pro-forma, tally marks | Layout is what breaks structured reads |
| Content — all named, all counts, mixed named + counts | Directly tests principle P10 |
| Language — English, Hindi/Tamil names, transliteration | Real site rolls |
| Quality — one deliberately near-illegible | Establishes the floor |

Include at least one sheet with **absences marked**, and one with a name
crossed out. Those decide whether the model transcribes intent or ink.

### What the numbers mean

| Metric | Why it decides something |
|---|---|
| **Name recall** | A missed worker goes unpaid. This is the go/no-go number. |
| **Name precision** | An invented name is worse than a missed one — it enters the register and poisons matching for every later report. |
| **Trade accuracy** | Scored only on correctly-read names; a trade on a phantom worker is meaningless. |
| **Headcount error** | Signed, because consistent under-counting on group rows is a different fix from misreading letters. |
| **Row-type errors** | Named person read as a group, or vice versa. Cheap to miss, and it silently drops names. |

## 4. Results — NOT YET RUN

Fill this in from a real run before any further Labour investment.

| Date | Sheets | Name recall | Name precision | Trade acc. | Headcount err. | Row-type err. | Prompt version |
|---|---|---|---|---|---|---|---|
| _pending_ | | | | | | | |

### Observed failure modes

_To be filled in. Record the actual photo and what came back, not a
paraphrase._

## 5. Decision thresholds — agree these before seeing the numbers

Set in advance so the result is read honestly rather than rationalised.

| Outcome | Reading | Action |
|---|---|---|
| Recall ≥ 95%, precision ≥ 95% | Trustworthy | Proceed as designed. Confirmation screen is sufficient safety. |
| Recall 80–95% | Useful but not trustworthy alone | Proceed **with** the correction step in §6. Do not present the read as authoritative. |
| Recall < 80%, or any invented names | Not usable for named capture | Fall back: photo becomes an *attachment* plus a headcount, names typed or spoken. The sheet is still stored as evidence (ADR-L3), so nothing is lost. |
| Structure lost but text readable | A plumbing problem, not a reading one | Re-check §2 before touching prompts. |

**Invented names deserve their own veto.** A missed name is a gap someone
notices at payment. An invented one becomes a register entry, then matches
future reports, and quietly corrupts history — exactly the failure principle
P4 exists to prevent.

## 6. If it is unreliable — the lightweight correction step

Proposed rather than built, per the instruction to prefer confirmation over
assumption. Do not build it until §4 says it is needed.

The confirmation preview already lists every line. The smallest useful
addition is to make an uncertain read *visible* rather than silent:

- Vision emits `"?"` for a name it could not read (already instructed in the
  prompt). The preview renders that row as **"1 unnamed worker (couldn't read
  the name)"** rather than hiding it.
- If any row is uncertain, the confirmation gains one extra option beside
  Yes/No: **"Fix a name"** — which asks for the row and the correct spelling,
  reusing the existing slot machinery rather than a new flow.
- Headcount stays authoritative even when names fail, so the attendance is
  still recordable at reduced fidelity. That is principle P9: a fast record
  with a gap beats a perfect record nobody completes.

This deliberately does **not** propose per-worker confirmation. Fifteen
questions makes the feature unusable, and P4/P9's stated resolution is to
invest in the read being good enough that asking is rare.

## 7. What is blocked

Everything downstream of this question, by choice: stubbed worker-register
integration and matching is the agreed next step **after** §4 is filled in.

**To unblock: 10–15 real attendance sheet photographs**, varied per §3. That
is the only missing input.
