"""Shared assistant enumerations (input modality, semantic type).

``InputModality`` is used by both ``NormalizedMessage`` (M2, produced) and
``UnderstandingResult`` (M3, consumed) so it lives here to avoid divergence.

Ownership: CROSS-REVIEW (shared between M2 producer and M3 consumer).
"""

from __future__ import annotations

from enum import Enum


class InputModality(str, Enum):
    TEXT = "text"
    VOICE = "voice"
    IMAGE = "image"
    DOCUMENT = "document"
    INTERACTIVE = "interactive"  # button / list reply
    UNKNOWN = "unknown"


class SemanticType(str, Enum):
    """What the understanding pipeline believes the message is *about*.

    These are understanding hypotheses, not workflow selections — the planner
    (M6) owns final workflow choice.
    """

    EXPENSE = "expense"
    EQUIPMENT_USAGE = "equipment_usage"
    MATERIAL_UPDATE = "material_update"
    # A supplier's document listing several materials, not a sentence about
    # one. Distinct from MATERIAL_UPDATE because the shapes differ in kind: a
    # MATERIAL_UPDATE carries one material and a direction, an invoice carries
    # a `line_items` array plus supplier and totals, and always means received.
    # Splitting them keeps the single-material prompt (the far more common
    # message) from having to describe an array it will never produce.
    MATERIAL_INVOICE = "material_invoice"
    LABOUR_UPDATE = "labour_update"
    GENERAL_SITE_UPDATE = "general_site_update"
    # ADR-D14 (docs/execution/DAILY_REPORTING_PLAN.md): the user is correcting
    # a quantity/value already reported ("make that 180", "actually it was
    # 40 sqm, not 30") -- distinct from GENERAL_SITE_UPDATE's "progress"
    # update_kind, which reports a genuinely NEW measurement at this moment.
    # Explicit correction language only; a plain restated number with no
    # "actually"/"make that"/"correct that to" framing stays GENERAL_SITE_
    # UPDATE. Never creates a new record -- always targets the most recent
    # quantity-bearing Progress Update this conversation produced (resolved
    # by seeding, same as ACTIVITY_CONTINUATION_REQUESTED's target).
    ACTIVITY_CORRECTION = "activity_correction"
    # A problem, delay, or blocker that stops or slows down work (e.g. "ran
    # out of cement", "JCB broke down", "raining since morning") -- a
    # business-affecting write, unlike ACTIVITY_QUERY's "any open issues?"
    # question. Distinct from GENERAL_SITE_UPDATE the same way EXPENSE is
    # distinct from FINANCE_QUERY: this reports a problem, GENERAL_SITE_UPDATE
    # reports work done or in progress -- never confuse the two.
    SITE_ISSUE = "site_issue"
    # Acknowledge, resolve, mark won't-fix, cancel, or reopen an existing
    # Site Issue -- always targets the single most recently reported issue
    # in the right status (resolved by seeding, never stated by the user),
    # the same "most recent record of a kind" pattern REVERSAL uses. Splits
    # into five CanonicalEventTypes by the extracted `action` field
    # ("acknowledge"|"resolve"|"wont_fix"|"cancel"|"reopen"), the same way
    # REVERSAL splits by `target_kind` (see canonicalization/mapping.py).
    # `cancel` and `reopen` are the two repair directions: cancel withdraws
    # a mistaken report, reopen undoes a premature close. Never creates a
    # new site_issues row -- SITE_ISSUE (above) is the only report/create
    # path, and cancel is a status transition, never a delete (P1).
    SITE_ISSUE_UPDATE = "site_issue_update"
    GENERAL_QUESTION = "general_question"
    # A deterministically recognized "who am i"/"my profile"/etc (see
    # mesiri_ai.whoami_classifier) -- distinct from GENERAL_QUESTION/UNKNOWN
    # so the answer is the caller's own identity summary, not the generic
    # capability reply or an undifferentiated "didn't understand". Set
    # without an AI call; the reply itself is still built downstream
    # (runtime/inbound_journey.py), since it needs the resolved
    # ActorIdentity, which Understanding must not know about.
    WHOAMI_QUESTION = "whoami_question"
    # A question about current stock or movement history for a material (e.g.
    # "how much cement is left?") -- read-only, never an update. Distinct from
    # MATERIAL_UPDATE the same way WHOAMI_QUESTION is distinct from a report:
    # it carries no business record to save, only a query to answer.
    INVENTORY_QUERY = "inventory_query"
    # A question about who worked (e.g. "how many workers today?", "labour
    # cost this week") -- read-only, never an update. Distinct from
    # LABOUR_UPDATE for the same reason INVENTORY_QUERY is distinct from
    # MATERIAL_UPDATE, and the distinction is load-bearing here: misreading
    # "14 workers today?" as a report would try to *record* 14 workers
    # instead of counting them.
    LABOUR_QUERY = "labour_query"
    # A question about progress already logged or open site issues (e.g.
    # "what did I log today?", "what happened on site X yesterday?", "any
    # open issues on site Y?") -- read-only, never a report. Distinct from
    # GENERAL_SITE_UPDATE the same way LABOUR_QUERY is distinct from
    # LABOUR_UPDATE: a narrative report should never be misread as a
    # question about the log, and vice versa.
    ACTIVITY_QUERY = "activity_query"
    # A request to be sent today's Daily Progress Report as a document
    # (e.g. "send me today's DPR", "share today's report") -- #16 Daily
    # Report Generation's chat trigger. Read-only, never an update, and
    # deliberately distinct from ACTIVITY_QUERY: a DPR request wants the
    # generated PDF document itself, not a text summary of the log.
    DPR_REQUEST = "dpr_request"
    # A question about cash/account balances or past expenses (e.g. "how much
    # cash do I have?", "balance of Site Cash", "how much did we spend on
    # diesel?") -- read-only, never an update. Splits into two
    # CanonicalEventTypes by the extracted `query_kind` field ("balance" or
    # "expenses"), the same way MATERIAL_UPDATE splits by `direction` (see
    # canonicalization/mapping.py).
    FINANCE_QUERY = "finance_query"
    # Moving money between two of the org's own accounts (e.g. "transfer
    # ₹50,000 from Company Account to Site Cash") -- a business-affecting
    # write, unlike FINANCE_QUERY, so it still goes through draft/confirm.
    TRANSFER = "transfer"
    # Petty cash issued to or returned by a person (e.g. "give ₹20,000
    # petty cash to Alan", "Alan returns ₹3,000") -- built as a convenience
    # shape over TRANSFER (Finance Module Slice 5, see
    # workflows/petty_cash/nodes.py): the recipient's employee-advance
    # account is one leg of the transfer, auto-created on first issuance.
    # Splits into two CanonicalEventTypes by the extracted `direction` field
    # ("issue" or "return"), the same way MATERIAL_UPDATE splits by
    # `direction` (see canonicalization/mapping.py).
    PETTY_CASH = "petty_cash"
    # Undo the user's most recently recorded expense or transfer (e.g.
    # "reverse my last expense", "cancel that transfer") -- Finance Module
    # Slice 7. Splits into two CanonicalEventTypes by the extracted
    # `target_kind` field ("expense" or "transfer"), the same way
    # MATERIAL_UPDATE/PETTY_CASH split by their own field (see
    # canonicalization/mapping.py). Deliberately targets only the *most
    # recent* record of that kind -- no slot-fill/disambiguation UI for
    # picking among several, per the V1 scope in
    # docs/execution/FINANCE_MODULE_PLAN.md.
    REVERSAL = "reversal"
    # Managing the org's own money accounts themselves -- create/rename/
    # deactivate (e.g. "rename Main HDFC Bank Account to Office Cash") --
    # never a transaction against one. Until 2026-07-26 this bypassed
    # Understanding entirely (a hand-written English-only regex parser,
    # runtime/account_admin_parser.py, still runs first as a zero-token fast
    # path for the exact phrasing it recognizes); this semantic type is the
    # AI-understood fallback for everything else -- other phrasing, voice,
    # non-English -- the same as every other finance workflow. ADMIN/FINANCE
    # only, enforced independently of Understanding (see
    # runtime/inbound_journey.py and application/finance/validation.py) --
    # this type alone existing here does not grant a lower-privileged role
    # the ability to act on it.
    ACCOUNT_ADMIN = "account_admin"
    # Creating a new Project record itself (e.g. "create a new project called
    # Skyline Towers") -- never an activity/site issue/expense *at* an
    # existing project, which is every other semantic type here. Mirrors
    # ACCOUNT_ADMIN's shape: ADMIN/PROJECT_MANAGER only, enforced
    # independently of Understanding (see runtime/inbound_journey.py and
    # application/projects/validation.py) the same way ACCOUNT_ADMIN is --
    # this type alone existing here does not grant a lower-privileged role
    # the ability to act on it. Deliberately create-only for now (no rename/
    # archive companion actions the way account_admin has) -- those aren't
    # built, and this type does not imply they exist.
    PROJECT_CREATE = "project_create"
    # Creating a new Site record under an EXISTING project (e.g. "create a
    # new site called Block A"). Which project is never stated as a
    # candidate field -- it comes from the same context resolution every
    # other project/site-scoped semantic type already relies on (explicit
    # "at project X" mention, active/workflow context, or the single-
    # authorized-project default; see context/resolver.py), same as
    # SITE_ISSUE/GENERAL_SITE_UPDATE. Same role restriction as
    # PROJECT_CREATE (ADMIN/PROJECT_MANAGER), enforced independently of
    # Understanding (see runtime/inbound_journey.py and
    # application/projects/create_site_validation.py).
    SITE_CREATE = "site_create"
    # A request for a full summary/status of a project or site itself (e.g.
    # "give me all details of Skyline Towers", "what's the status of Block
    # A", "tell me everything about this site") -- read-only, never an
    # update. Distinct from ACTIVITY_QUERY (a day's activity/issue log) and
    # FINANCE_QUERY (just balance/expenses): this is the project/site
    # RECORD itself (name, code, client, location, status, sites, team)
    # plus its current operational snapshot (open issues, labour today,
    # activities today, stock, spend this month). The financial section is
    # visibility-gated by role (see runtime/inbound_journey.py's
    # _seed_project_detail_query) -- a SITE_ENGINEER still gets a full
    # reply, just without the money line, unlike PROJECT_CREATE/SITE_CREATE
    # where a disallowed role is refused outright (this is a read, not a
    # write). Which project/site is never a candidate field -- resolved by
    # context the same way PROJECT_CREATE/SITE_CREATE's project scope is.
    PROJECT_DETAIL_QUERY = "project_detail_query"
    # A recurring scheduled instruction (e.g. "every day at 5pm send me the
    # DPR", "at 3pm tell me who hasn't reported", "every Monday remind
    # Ilan and Hysam to submit their report") -- never a one-time question
    # or report request (those use dpr_request/activity_query/project_
    # detail_query etc, which answer once, right now). Distinct from every
    # other semantic type here the same way ACCOUNT_ADMIN is distinct from
    # a transaction: this manages a standing RULE, not a single business
    # record. Targeting anyone other than the sender (a named person, a
    # role, or "whoever hasn't reported") is ADMIN/PROJECT_MANAGER only,
    # enforced independently of Understanding (see
    # runtime/inbound_journey.py and
    # application/automations/create_validation.py) -- this type alone
    # existing here does not grant a lower-privileged role the ability to
    # target anyone but themselves.
    AUTOMATION_SETUP = "automation_setup"
    # Adding an EXISTING org user as a member of an EXISTING project (e.g.
    # "add Rajesh to Skyline Towers as site engineer") -- never creating a
    # new user (WhatsApp cannot provision identity/WhatsApp-number auth;
    # that stays dashboard-only) and never a project/site itself (those are
    # PROJECT_CREATE/SITE_CREATE). Which project is never a candidate field
    # here -- resolved by context the same way SITE_CREATE's project scope
    # is. member_name is a best-effort hint, resolved against the org's
    # real active users at confirm time (same "hard rejection, never a
    # silent default" treatment as ACCOUNT_ADMIN's target_name -- see
    # application/projects/name_resolution.py), not the workforce register
    # (workflows/worker_promotion) which is a different, non-app-user list.
    # Same role restriction as PROJECT_CREATE/SITE_CREATE (ADMIN/
    # PROJECT_MANAGER), enforced independently of Understanding (see
    # runtime/inbound_journey.py and
    # application/projects/add_member_validation.py).
    ADD_PROJECT_MEMBER = "add_project_member"
    # Creating a brand new person/user with WhatsApp access (e.g. "add
    # Rajesh, 9198765xxxxx, as site engineer") -- distinct from
    # ADD_PROJECT_MEMBER, which only ever adds an EXISTING user to a
    # project. Provisioning a new identity/access grant is a materially
    # bigger blast radius than adding an already-vetted person to one more
    # project, so this is ADMIN/PROJECT_MANAGER only, same enforcement
    # split as every other write here (see runtime/inbound_journey.py and
    # application/identity/create_user_validation.py). The new user gets no
    # email/password and cannot log into the dashboard until an admin adds
    # those later -- WhatsApp text can supply a name and phone number
    # reliably, never a real email or a secure password.
    CREATE_USER = "create_user"
    UNKNOWN = "unknown"
