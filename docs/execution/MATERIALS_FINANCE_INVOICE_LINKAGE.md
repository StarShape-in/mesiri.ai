# Materials ↔ Finance Invoice Linkage — Architecture Investigation

**Status:** INVESTIGATION FINDING — informs [MATERIALS_PHASE_4_INVOICE_CAPTURE_PLAN.md](MATERIALS_PHASE_4_INVOICE_CAPTURE_PLAN.md). No code.
**Author:** Claude (Opus 5), 2026-07-30.
**Question:** can one confirmed invoice create both the inventory records and a linked finance
expense, without duplicating invoice data or double-counting?

---

## Verdict

**Yes — the existing architecture supports this cleanly, and integration is clearly better than
parallel records.** No new infrastructure, no event bus, no eventual consistency, no schema
duplication.

The decisive fact: **`RecordExpenseHandler.handle()` takes an `AsyncConnection` as its first
parameter.**

```python
# backend/src/mesiri/application/expenses/handlers.py:53
async def handle(self, conn: AsyncConnection, cmd: RecordExpenseCommand) -> ExecutionResult:
```

Both existing callers — the REST router and the WhatsApp CQRS path — construct the handler and
pass in a connection they already hold. That is precisely the convention
`post_material_movement(conn, ...)` follows, and its docstring states the principle outright:
*"reuse whichever atomicity mechanism the caller already has."*

So a Materials invoice execution can create the expense **on its own connection, inside its own
transaction**. The invoice, the receipts, the ledger movements and the expense either all land
or none do.

---

## What the investigation found

### 1. An expense does not have to move money — which is exactly right for a supplier invoice

`Expense` and `ExpensePayment` are separate entities. The entity docstring says it plainly:
*"Expense is the business event (what money was spent on); ExpensePayment is the money movement
out of a MoneyAccount to cover it (zero, one, or several per expense)."*

`PaymentStatus` includes `UNPAID`, and `account_id` on the create path is optional — *"Omit to
leave the expense unpaid."*

This maps onto construction reality with no forcing: a supplier invoice on 30-day credit
creates a **liability now** and a **payment later**. The Finance module already models exactly
that. Nothing needs inventing.

### 2. Finance already has every field an invoice-sourced expense needs

`expenses` carries `vendor_id`, `occurred_date`, `amount`, `currency`, `description`,
`category_id`, `project_id`, `site_id`, `correlation_id`, `source`, `expense_number`,
`tax_rate`, `tax_amount`, `is_tax_inclusive`, and `receipt_media_object_key`.

That last one matters: **the invoice image needs no duplication.** Materials stores
`invoice_object_key`; Finance stores the same object key. One file in object storage, two
references to it — which is a reference, not a copy.

### 3. Duplicate detection already exists

`PostgresExpenseRepository.find_potential_duplicate(amount, occurred_date, vendor_id | category_id)`
was built for Finance Slice 8. It is directly reusable as the guard against the same invoice
being recorded twice through two different routes.

### 4. The polymorphic source-reference pattern is already established in this codebase

`material_movements` carries `source_type` / `source_id` as a *"polymorphic pointer, no FK"* —
introduced specifically so future sources could post into the ledger without a schema change.

The same pattern solves the direction-of-dependency problem here (§ Recommended Architecture).

### 5. The event bus exists but is the wrong tool here

`backend/src/mesiri/events/bus/` is built, tested, and has **zero registered consumers**
(`_registered_consumers()` returns `[]`). It would work — but it buys decoupling at the cost of
eventual consistency, and it would make this feature the bus's first production consumer.

For a case where both records describe **one atomic business event the user just confirmed**,
a window where inventory exists but the expense does not is a defect, not a trade-off. The
transactional path is available and strictly better here. *(The bus remains the right tool for
notifications and search indexing, which is what it was built for.)*

### 6. One stated architectural rule needs care

`AGENTS.md` records for Daily Reporting: *"never writes into the materials/labour/equipment/
finance ledgers — references only (ADR-D2/P3)."*

That rule is about a **reporting** module not manufacturing business records it doesn't own —
correct, and not what is proposed here. But the underlying principle is sound and should be
honoured: **Materials must never write to the `expenses` table directly.** It calls Finance's
own handler, which applies Finance's validation, category and vendor resolvers, idempotency,
sequential expense numbering, and outbox event. That is *asking the owner*, not *reaching into
the ledger* — a materially different thing, and the distinction is what keeps this clean.

*Also noted:* `AGENTS.md` states Finance never emits to `outbox_events`. That is **stale** —
`expense_execution.py:199` emits `ExpenseRecorded`, registered in the timeline projector. The
document should be corrected.

---

## Recommended Architecture

### The invoice is the shared source of truth, owned by Materials

`material_invoices` (supplier, invoice date, invoice total, object key) lives in Materials.
That is the right home: an invoice's line items are materials, its quantities feed stock, and
Finance's own module scope in `AGENTS.md` says *"Purchases/procurement... explicitly out of
scope here."*

### Each module references it according to its own responsibility

```
                    material_invoices                    ← the document (Materials-owned)
                    ├─ supplier / vendor_id
                    ├─ invoice_date
                    ├─ invoice_total                     ← what is owed
                    └─ invoice_object_key                ← ONE file in object storage
                         │
       ┌─────────────────┴──────────────────┐
       │                                    │
  MATERIALS                             FINANCE
  "what arrived"                        "what it cost us"
       │                                    │
  material_receipts.invoice_id         expenses
   (one per line item)                  ├─ amount = invoice_total   (ONE expense)
       │                                ├─ payment_status = unpaid
  material_movements                    ├─ vendor_id  (same vendor)
   (stock truth)                        ├─ source_document_type = 'material_invoice'
                                        ├─ source_document_id     = <invoice id>
                                        └─ receipt_media_object_key = <same object key>
```

**Two new nullable columns on `expenses`: `source_document_type` and `source_document_id`.**
No foreign key, exactly like `material_movements.source_type/source_id`. Finance therefore does
**not** depend on Materials — it records only *"this expense originated from document X of type
Y"*, which stays true if Materials is never touched again.

### Orchestration lives in the application layer, not in either domain

A thin use case — `application/purchasing/record_invoice.py` — receives the confirmed invoice
and, on one connection inside one transaction:

1. inserts `material_invoices`
2. inserts N `material_receipts` + N `post_material_movement()` calls *(existing Phase 4 plan)*
3. calls `RecordExpenseHandler.handle(conn, expense_cmd)` **once**, for the invoice total
4. writes the outbox event

Neither domain imports the other. The application layer already owns transactions by design —
`application/materials/handlers.py` states *"transaction ownership is centralized here"* — so
this is the layer's existing job, not a new responsibility.

### Idempotency

The expense command's `idempotency_key` is derived deterministically from the invoice id
(e.g. `invoice:<uuid>:expense`). A retried confirmation replays through Finance's existing
idempotency claim and cannot create a second expense.

---

## Double-Counting Analysis

This is where the real risk lives, and it is worth being precise: **linking does not create the
double-counting risk — it is the only thing that makes it detectable.**

| Vector | Status | Handling |
|---|---|---|
| **One expense per invoice, not per line** | Design rule | Finance sums `expenses.amount`. Three lines → one expense of the invoice total. Counted once. **Never create an expense per line item.** |
| **Same invoice sent twice via different picker routes** ("Expense" then "Material Delivery") | **Real risk, exists today** | Reuse `find_potential_duplicate` on vendor + date + amount; the source-document link makes an invoice-sourced expense identifiable, so a second attempt is caught |
| **Materials "purchase value" + Finance "total expenses" added together** | **New risk this linkage creates** | These become **two views of the same money**, not two amounts. Any combined figure must count one or the other, never both. Cross-module spend reporting must exclude material-sourced expenses *or* exclude material purchase value. **Flagged for Phase 6.** |
| **Invoice total ≠ sum of line totals** (tax, freight) | Expected, not an error | The **expense is the invoice total** — that is what is owed. **Inventory values the lines.** These are different questions with different correct answers; they must never be reconciled against each other |
| **Expense reversed but stock kept, or vice versa** | Real | Reversal semantics differ by design: Materials reverses with an opposite ledger movement, Finance voids/reverses an expense. **Recommendation: do not auto-cascade in V1.** Surface the link so a user reversing one is told the other exists. Auto-cascading corrections across modules is how silent, hard-to-trace corruption starts |

---

## Alternatives Considered and Rejected

| Option | Why rejected |
|---|---|
| **Materials writes `expenses` directly** | Bypasses Finance's validation, resolvers, expense numbering and events. Violates the ledger-ownership principle. Would need reimplementing Finance's rules in Materials |
| **Finance owns the invoice; Materials references it** | Invoices are line-item material documents. Finance's own recorded scope excludes purchases. Would force Materials to depend on Finance for its core purchase flow — the wrong direction |
| **Event bus (`MaterialInvoiceConfirmed` → consumer creates expense)** | Works, but introduces an eventual-consistency window where stock exists and spend does not, for one atomic user-confirmed action. Would also make this the bus's first production consumer. Right tool for notifications; wrong tool here |
| **Parallel records, no link** (status quo) | The thing to avoid. Silently permits the same invoice being both an expense and a purchase, with nothing able to detect it |
| **Shared "commercial document" table in `core`** | Defensible (mirrors ADR-D3's shared `location_nodes`), but premature: there is exactly one document type today. Revisit if subcontractor bills or equipment invoices arrive |

---

## Impact on the Phase 4 Plan

Additive, not a redesign. The invoice model, extraction, confirmation and multi-line execution
all stand.

**Added:** two nullable columns on `expenses`; the orchestration use case; expense creation in
the confirmed-invoice path; a "Linked expense" row on Purchase Details and a "From invoice" link
on Expense Detail.

**One product decision this forces (§ Decisions):** should confirming a material invoice
*always* create an expense, or should the user be asked?

---

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Cross-module spend reports double-count | **High** | Documented rule; enforced in Phase 6 analytics; the source-document link makes exclusion mechanical |
| Materials work regresses Finance | **High** | Materials calls Finance's handler, never its tables. Full Finance + expenses suites run and reported |
| Category mis-resolution puts material spend in the wrong bucket | Medium | Pass explicit `category_text: "Materials"`; confirm the org has that category or that the default is acceptable |
| Expense created but user only wanted stock | Medium | The decision below; if opt-out is chosen, default it explicitly rather than inferring |
| Reversal divergence between modules | Medium | No auto-cascade in V1; surface the link on both sides |
| Two more shared-domain surfaces touched | Medium | Finance/expenses are **not** Labour — isolation rule unaffected. Still: read-and-call only, no Finance file modified beyond the two columns and their response mapping |

---

## Decisions — APPROVED 2026-07-30

1. **Does a confirmed material invoice always create an expense?** → **Yes, always, unpaid.**
   Approved. The founder's reasoning is the deciding one: a company buying ₹1,00,000 of cement
   should not have one employee key it into Materials and another key the same invoice into
   Finance. Upload once, both departments update. Opt-out, if ever wanted, belongs in org
   settings — never in the per-invoice flow.
2. **Expense category** → explicit `category_text: "Materials"`, seeded if absent. Approved.
3. **Reversal cascade** → **none in V1.** Show the link on both sides so whoever reverses one
   is told the other exists. Approved.
4. **Phase placement** → **inside Phase 4**, not a later 4b. Approved. One confirmation must
   produce both records from day one; splitting them would ship the double-entry problem and
   then remove it.
5. **Correct the stale `AGENTS.md` line** about Finance not emitting outbox events — to be done
   as part of the Phase 4 documentation update.

---

**Status: approved. Implementation proceeds as part of Phase 4, subject to the one remaining
shared-file approval (`interactions/handler.py`, see the Phase 4 plan § 14.4).**
