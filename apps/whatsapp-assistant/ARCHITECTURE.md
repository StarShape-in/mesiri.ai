# WhatsApp Assistant — Architecture Guide

> **This is the engineering constitution of `apps/whatsapp-assistant/`.**  
> Every developer and every AI coding agent working in this folder must read it first.  
> All architectural decisions described here are inferred from the current implementation, not from plans or intentions.

---

## Table of Contents

1. [Purpose](#1-purpose)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Folder Responsibilities](#3-folder-responsibilities)
4. [What This Folder Must NOT Do](#4-what-this-folder-must-not-do)
5. [Folder Structure](#5-folder-structure)
6. [Runtime Journey](#6-runtime-journey)
7. [Current Architecture Status](#7-current-architecture-status)
8. [Contracts](#8-contracts)
9. [Ports and Adapters](#9-ports-and-adapters)
10. [Dependency Rules](#10-dependency-rules)
11. [Design Principles](#11-design-principles)
12. [Common Mistakes](#12-common-mistakes)
13. [Development Checklist](#13-development-checklist)
14. [Future Roadmap](#14-future-roadmap)
15. [Glossary](#15-glossary)

---

## 1. Purpose

### What is the WhatsApp Assistant?

The WhatsApp Assistant is the **primary human-facing interface** of Mesiri. It is a FastAPI service that receives inbound WhatsApp messages from construction site workers, understands them using AI, resolves business context, and eventually routes them through workflows that capture structured business data — material updates, expenses, labour reports, equipment usage.

It is not a chatbot. It is a **field data capture system** that happens to use a conversational channel.

### Why does it exist?

Construction site workers do not use desktop apps. They use WhatsApp on their phones while on-site. The WhatsApp Assistant eliminates data entry friction: a site engineer sends a voice note saying "received 20 bags cement" and the system converts that into a structured material receipt record without the engineer filling a form.

### What business problem does it solve?

- **Real-time site data capture** without desktop apps, forms, or delays
- **Multi-modal input** — text, voice, and photos all accepted
- **Language support** — Malayalam and other regional languages via STT and translation
- **Authorization gate** — only registered, org-affiliated users can submit data

### Where does it sit inside Mesiri?

```
[WhatsApp Cloud API] ← Meta's servers
         │
         ▼
[WhatsApp Assistant]  ← this folder — the AI conversation layer
         │
         ▼
[Backend Domain API]  ← business records, user management
         │
         ▼
[PostgreSQL + Redis]  ← persistence
         │
         ▼
[Mobile App]          ← managers review structured data
```

The assistant is the **front door for field workers**. The backend is the **source of truth for business data**. They are separate services sharing the same PostgreSQL database.

---

## 2. High-Level Architecture

The following diagram shows the **complete intended architecture** of this folder. Markers show the current implementation status.

```
[WhatsApp Cloud API — Meta's servers]
              │
              │  POST /webhook (HMAC-SHA256 signed)
              ▼
┌─────────────────────────────────────────────┐
│  M2 — INGRESS  ✅ IMPLEMENTED               │
│  webhook.py → verification → deduplication  │
│  → normalization → media download/upload    │
│  Produces: NormalizedMessage.v1             │
└───────────────────┬─────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│  IDENTITY GATE  ✅ IMPLEMENTED              │
│  PostgresActorReader → ActorIdentity        │
│  Gates: unregistered / no-org / suspended   │
│  Produces: ActorIdentity or early reply     │
└───────────────────┬─────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│  M3 — UNDERSTANDING  ✅ IMPLEMENTED         │
│  UnderstandingPipeline                      │
│  text → extraction                          │
│  voice → STT → extraction                  │
│  image → vision → extraction               │
│  Produces: UnderstandingResult.v1           │
└───────────────────┬─────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│  M4 — CONTEXT  ⚠️ PARTIAL                  │
│  Two resolvers exist (see §7):              │
│  • ContextResolver (M4, Postgres/Redis)     │
│    — built but NOT called in runtime        │
│  • ContractContextResolver (contract ports) │
│    — called but using FAKE adapters only    │
│  Produces: ResolvedContext (two schemas)    │
└───────────────────┬─────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│  M5 — PLANNER  🔲 NOT IMPLEMENTED          │
│  planner/ folder exists, all files 0 bytes  │
│  PlannerDecision contract: 0 bytes          │
│  Will consume: ResolvedContext              │
│  Will produce: PlannerDecision              │
└───────────────────┬─────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│  M6 — WORKFLOW RUNTIME  🔲 NOT IMPLEMENTED │
│  workflows/ folder exists, all 0 bytes      │
│  LangGraph not installed or referenced      │
│  Will consume: PlannerDecision              │
│  Will produce: WorkflowState + DraftAction  │
└───────────────────┬─────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│  M7 — INTERACTION  🔲 NOT IMPLEMENTED      │
│  interactions/ folder exists, all 0 bytes   │
│  Will consume: DraftAction + InteractionSpec│
│  Will produce: user confirmation request    │
└───────────────────┬─────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│  APPLICATION LAYER  🔲 NOT IMPLEMENTED     │
│  Domain service calls, command dispatch     │
│  Business record creation (via backend API) │
└───────────────────┬─────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│  REPLY  ✅ IMPLEMENTED (M3-based only)     │
│  format_reply(UnderstandingResult)          │
│  WhatsAppSender.send_text()                 │
└─────────────────────────────────────────────┘
              │
              ▼
[WhatsApp Cloud API → worker's phone]
```

**Current production reality:** The path terminates at reply after M3/M4. Context runs but its output has no effect on the reply. Planner, Workflow, and Interaction have not started.

---

## 3. Folder Responsibilities

This folder owns:

| Responsibility | Status |
|---|---|
| WhatsApp webhook reception and verification | ✅ |
| Message deduplication | ✅ |
| Raw payload normalization → `NormalizedMessage` | ✅ |
| Media download from Meta CDN | ✅ |
| Media upload to object storage | ✅ (fake storage) |
| Identity gate (register/org/active check) | ✅ |
| Speech-to-text orchestration | ✅ |
| Vision / OCR orchestration | ✅ |
| Structured field extraction | ✅ |
| Confidence scoring | ✅ |
| Context resolution (business who/where) | ⚠️ partial |
| Planner (route to workflow) | 🔲 |
| Workflow runtime (LangGraph) | 🔲 |
| Human-in-the-loop interaction | 🔲 |
| Memory (conversation history) | 🔲 |
| Business record creation | 🔲 |
| WhatsApp reply rendering | ✅ (M3-based) |
| HTTP API for control-plane (auth, users, projects) | ✅ |

This folder does **not** own:
- The business domain schema (PostgreSQL tables, Alembic migrations)
- The backend REST API (`backend/`)
- The mobile application (`apps/mobile/`)
- AI provider SDKs (`platform/ai/`)
- Shared contracts (`shared/contracts/`)

---

## 4. What This Folder MUST NOT Do

These are hard architectural boundaries. Violating them creates entanglement between layers that is extremely difficult to unpick later.

### MUST NOT: Write SQL

```python
# WRONG — never in whatsapp-assistant/src
conn.execute("SELECT * FROM users WHERE whatsapp_number = :wa_id", ...)

# CORRECT — read through a port
actor = await actor_reader.resolve_by_whatsapp_id(wa_id)
```

**Why:** SQL belongs in `backend/postgres/actor.py`. The assistant may only know about `ActorIdentity`, `ProjectSummary`, `SiteSummary`, and `ActorReader` — defined in `backend/ports.py`. If the schema changes, only the adapter changes. The assistant is untouched.

### MUST NOT: Import SQLAlchemy models or ORM entities

```python
# WRONG
from mesiri.infrastructure.postgres.models.user import User

# CORRECT
from backend.ports import ActorIdentity
```

**Why:** ORM models carry schema knowledge (column names, joins, types). The assistant must not know about table structure.

### MUST NOT: Define new shared contracts

```python
# WRONG — creating a contract inside the assistant
# apps/whatsapp-assistant/src/my_new_contract.py
class MyEvent(BaseModel): ...

# CORRECT — put contracts in shared/
# shared/contracts/src/mesiri_contracts/assistant/my_event.py
```

**Why:** Contracts are the boundary between modules. They must live in `shared/contracts
/` so both producer and consumer import from the same location. Contracts inside the assistant can only be consumed by the assistant — making them useless as contracts.

### MUST NOT: Call AI provider SDKs directly

```python
# WRONG
import google.generativeai as genai
model = genai.GenerativeModel("gemini-2.0-flash")

# CORRECT — use the port
result = await self._extraction.extract(text, correlation_id=correlation_id)
```

**Why:** Provider selection, retry logic, fallback, model routing, and credential management all live in `platform/ai/`. The assistant only knows provider ports. Calling SDKs directly bypasses retry/fallback, couples the assistant to a vendor, and makes testing require real API calls.

### MUST NOT: Persist business records

```python
# WRONG — creating a material receipt inside the assistant
await db.execute("INSERT INTO material_receipts ...")

# CORRECT — call the application layer (future)
await material_service.record_receipt(command)
```

**Why:** Business records belong to the domain. The assistant is a messaging interface — it collects and routes, it does not store domain data.

### MUST NOT: Put business rules in workflow nodes

```python
# WRONG — business logic in a LangGraph node
def validate_receipt_node(state):
    if state["quantity"] > 1000:
        raise ValidationError("Unrealistic quantity")

# CORRECT — validate in the domain service
await material_service.record_receipt(command)  # service owns rules
```

**Why:** Business rules change. If they live in workflow nodes, every rule change requires modifying the workflow graph. Domain services encapsulate rules; workflows orchestrate.

### MUST NOT: Bypass the correlation ID

```python
# WRONG — minting a new correlation ID inside a handler
correlation_id = str(uuid.uuid4())

# CORRECT — propagate the one already on the message
correlation_id = message.correlation_id
```

**Why:** The correlation ID is the thread that links WhatsApp message → understanding → context → workflow → business record → logs. Breaking it makes debugging impossible.

### MUST NOT: Import from `backend/src/mesiri/` except through `backend/ports.py`

The file `apps/whatsapp-assistant/src/backend/ports.py` is the **capability boundary**. The assistant may only cross into the backend through this file. Direct imports of `mesiri.domains.*`, `mesiri.infrastructure.*`, or `mesiri.bootstrap.*` from within `whatsapp-assistant/src/` outside of the postgres adapter (`backend/postgres/actor.py`) are a boundary violation.

---

## 5. Folder Structure

```
apps/whatsapp-assistant/
├── src/
│   ├── backend/            ← backend capability boundary
│   ├── channel/            ← outbound WhatsApp rendering
│   ├── context/            ← M4 context resolution (two implementations)
│   ├── ingress/            ← M2 inbound pipeline
│   ├── interactions/       ← M7 human-in-the-loop (stub)
│   ├── memory/             ← M8 conversation memory (stub)
│   ├── planner/            ← M5 routing planner (stub)
│   ├── projects/           ← HTTP API for project management
│   ├── runtime/            ← dependency injection, lifecycle, journey orchestration
│   ├── understanding/      ← M3 AI understanding pipeline
│   ├── users/              ← HTTP API for tenant user management
│   ├── workflows/          ← M6 LangGraph workflow runtime (stub)
│   ├── admin/              ← HTTP API for control plane
│   ├── auth/               ← HTTP API for mobile app authentication
│   └── main.py             ← ASGI entry point
├── tests/
│   ├── unit/               ← per-module unit tests (no HTTP, no DB)
│   ├── contract/           ← cross-module contract tests
│   └── integration/        ← live stack tests (marked, skipped by default)
├── scripts/                ← ad-hoc operational scripts
├── ARCHITECTURE.md         ← this file
├── Dockerfile
└── pyproject.toml
```

---

### `ingress/`

**Purpose:** Convert a raw Meta webhook payload into a `NormalizedMessage.v1` and hand it off for downstream processing.

**Responsibilities:**
- Verify webhook subscription challenges (`verification.py`)
- Verify HMAC-SHA256 payload signatures (`verification.py`)
- Deduplicate messages by `message_id` with a 24-hour TTL (`deduplication.py`)
- Download binary media (images, voice) from the Meta CDN (`media_ingestion.py`)
- Upload downloaded media to object storage and produce a `MediaReference` (`media_handoff.py`)
- Normalize Meta's JSON format into `NormalizedMessage.v1` (`normalization.py`)
- Orchestrate the above into a single background pipeline (`receiver.py`)

**Consumes:** Raw JSON from Meta webhook, binary media from Meta CDN

**Produces:** `NormalizedMessage.v1` (from `mesiri_contracts.assistant`)

**Never does:**
- Business logic
- Database access
- AI calls
- Context resolution

**Technical note — receiver.py:** There is an inline Postgres query inside `_process_message()` that enriches `NormalizedMessage.sender.profile_name` and `metadata["user_role"]` from the `users` table. This is a boundary violation (SQL inside ingress) and should be removed in a future cleanup. The identity gate in `_on_normalized()` in `dependencies.py` already handles user resolution properly through `ActorReader`.

**Future:** Replace `InMemoryDeduplicationStore` with a Redis-backed store when multi-instance deployment is needed. Replace `FakeObjectStorage` with the real R2 adapter.

---

### `understanding/`

**Purpose:** Convert a `NormalizedMessage` into a structured `UnderstandingResult` using AI providers. This is the semantic interpretation layer.

**Responsibilities:**
- Route by modality: text → extraction; voice → STT → extraction; image → vision → extraction
- Read media bytes through the `ObjectStoragePort` (never from disk, never directly from Meta)
- Inject AI providers through ports (never import SDKs directly)
- Score confidence deterministically using `ConfidencePolicy` from `platform/ai/`
- Catch provider failures and surface them as `UNUSABLE` results (never raise to caller)

**Consumes:** `NormalizedMessage.v1`

**Produces:** `UnderstandingResult.v1`

**Dependencies:**
- `mesiri_ai.ports.speech.SpeechUnderstandingProvider` (speech port)
- `mesiri_ai.ports.vision.VisionUnderstandingProvider` (vision port)
- `mesiri_ai.ports.extraction.StructuredExtractionProvider` (extraction port)
- `mesiri_contracts.common.storage.ObjectStoragePort`

**Never does:**
- Business logic
- Database access
- Context resolution
- Workflow selection
- User-facing replies

**Provider selection** (in `runtime.py`):
```
SARVAM_API_KEY set   → SarvamSpeechProvider     (live speech-to-text)
                else → FakeSpeechProvider        (deterministic fixture)

DEEPSEEK_API_KEY set → DeepSeekExtractionProvider
GEMINI_API_KEY set   → GeminiProvider
                else → FakeExtractionProvider

GEMINI_API_KEY set   → GeminiProvider            (vision)
                else → FakeVisionProvider
```

**Future:** Provider selection will move to a configurable `GatewayRouter` in `platform/ai/core/router.py`. Multi-provider fallback is already designed there.

---

### `context/`

**Purpose:** Determine *who is speaking*, *which organization/project/site* the message belongs to, *what they are authorized to do*, and how confident the resolver is in that answer. This is the authorization and scoping layer.

**This folder currently contains two distinct implementations:**

#### Implementation A — M4 `ContextResolver` (`resolver.py`)

The full production-grade implementation. Uses 9 narrow ports, Postgres repositories for all identity/project/site data, Redis for ephemeral active context, and a deterministic precedence policy.

- **Input:** `NormalizedMessage` + `UnderstandingResult`
- **Output:** `Result[ResolvedContext]` where `ResolvedContext` is `mesiri_contracts.assistant.resolved_context.ResolvedContext`
- **Ports:** `ExternalIdentityRepository`, `OrganizationMembershipRepository`, `RolePermissionRepository`, `ProjectRepository`, `SiteRepository`, `ContextPreferenceRepository`, `ActiveContextStore`, `ReplyContextProvider`, `WorkflowContextProvider`
- **Real adapters:** `postgres_repositories.py` — complete SQL implementations
- **Fake adapters:** `fakes.py` — deterministic in-memory implementations
- **Status:** Fully implemented and tested. **Not called in the current `_on_normalized` runtime path.**

#### Implementation B — `ContractContextResolver` (`contract_resolver.py`)

A simpler port-based resolver using the `mesiri_contracts.context` port interfaces.

- **Input:** `NormalizedMessage` + `UnderstandingResult`
- **Output:** `ResolvedContext` from `mesiri_contracts.context.resolved_context.ResolvedContext`
- **Ports:** `IdentityLookupPort`, `ScopeLookupPort`, `WorkflowStateReadPort` (from `mesiri_contracts.context.ports`)
- **Real adapters:** None — only fake adapters exist
- **Fake adapters:** `adapters/fake_identity.py`, `adapters/fake_scope.py`, `adapters/fake_workflow_state.py`
- **Status:** Called in the runtime path, but only with fake adapters. Context resolution always produces LOW confidence, unknown actor, unresolved scope.

> ⚠️ **KNOWN ARCHITECTURAL ISSUE:** Two different `ResolvedContext` schemas exist. This must be resolved before implementing Planner. Implementation A (M4) is the richer, more complete design and should become canonical.

#### `live_identity.py` — the identity bridge

This module is not a resolver. It is the **orchestration bridge** between the identity gate and the `ActorReader` port. It is called before the understanding pipeline, not after. It uses `backend.ports.ActorReader` (satisfied by `PostgresActorReader`) and returns `ActorIdentity`.

#### `context_policy.py` — precedence engine

Deterministic precedence: `MESSAGE_EXPLICIT > REPLY_CONTEXT > WORKFLOW_CONTEXT > ACTIVE_CONTEXT > USER_DEFAULT`. The policy is pure — given the same candidates it always returns the same result. Never asks an LLM.

#### `active_context.py` — ephemeral context store

Redis-backed. Stores the user's last selected project/site with TTL. Redis is **never authoritative** — the M4 resolver always revalidates against Postgres.

---

### `runtime/`

**Purpose:** Wire all modules together, define the `AppContainer`, and orchestrate the inbound journey.

**Files:**

- **`dependencies.py`** — `Settings`, `AppContainer`, `build_container()`. This is where all objects are constructed and injected. It is the only place allowed to know about concrete implementations.
- **`lifecycle.py`** — FastAPI application factory (`create_app()`), lifespan management, router mounting.
- **`inbound_journey.py`** — `process_inbound_message()`. Orchestrates: understanding → context → reply. This is a pure async function with no side effects beyond calling its injected callables.
- **`pipeline.py`** — Empty (0 bytes). Reserved for future pipeline abstraction.
- **`dispatcher.py`** — Empty (0 bytes). Reserved for future dispatch logic.

**Important:** `pipeline`, `sender`, and `actor_reader` are **closure-captured** inside `_on_normalized()` rather than being fields of `AppContainer`. This is a testability limitation — these objects cannot be replaced without rebuilding the container.

---

### `backend/`

**Purpose:** Define the capability boundary between the assistant and the backend infrastructure.

- **`ports.py`** — Defines `ActorReader` (Protocol), `ActorIdentity`, `ProjectSummary`, `SiteSummary`. This is what the assistant is allowed to know about the backend.
- **`postgres/actor.py`** — `PostgresActorReader`. The **only file** in the assistant that is allowed to write SQL, hold a SQLAlchemy engine, or know about table names. All schema knowledge is isolated here.

**Rule:** If the `users` table gains a new column, only `postgres/actor.py` changes. Nothing else in the assistant needs to change.

---

### `channel/`

**Purpose:** Render assistant outputs into WhatsApp-specific message formats and send them via the Meta Cloud API.

**Files:** `outbound.py` (HTTP client wrapper for Meta API), `renderer.py`, `buttons.py`, `text.py`, `images.py`, `lists.py`, `documents.py`.

**Consumes:** Plain strings, structured reply specs (future)

**Produces:** HTTP calls to `graph.facebook.com`

---

### `planner/` — Stub

**Purpose (future):** Receive `ResolvedContext` + `UnderstandingResult` and decide which workflow to start, which interaction to present, or whether to reply directly.

**Current state:** All files are 0 bytes. The `PlannerDecision` shared contract is also 0 bytes.

---

### `workflows/` — Stub

**Purpose (future):** Host LangGraph-based workflow graphs for domain-specific data capture (materials, expenses, labour, equipment).

**Current state:** All files are 0 bytes. LangGraph is not installed. No workflow state contract exists.

---

### `interactions/` — Stub

**Purpose (future):** Manage human-in-the-loop confirmations, field clarifications, and corrections before a workflow commits data.

**Current state:** All files are 0 bytes.

---

### `memory/` — Stub

**Purpose (future):** Provide conversation history and semantic context retrieval to the Planner so it can understand multi-turn conversations.

**Current state:** All files are 0 bytes. The `platform/memory/` package is also entirely empty.

---

### `admin/`, `auth/`, `users/`, `projects/`

These are **HTTP API modules** for the control-plane dashboard and mobile app, not part of the WhatsApp inbound pipeline. They are FastAPI routers mounted by `lifecycle.py`.

- `auth/router.py` — JWT login/register for mobile app
- `admin/router.py` — Organization-scoped admin endpoints
- `users/router.py` — Tenant user CRUD + access policy
- `projects/router.py` — Project and site management

---

## 6. Runtime Journey

This is exactly what happens when a WhatsApp message arrives today. No assumptions, no future state.

### Step 1 — Meta sends the webhook

```
POST /webhook
X-Hub-Signature-256: sha256=<hmac>
Content-Type: application/json

{"object": "whatsapp_business_account", "entry": [...]}
```

### Step 2 — Signature verification

`verify_request_signature()` in `ingress/verification.py` recomputes HMAC-SHA256 over the raw request body using `WHATSAPP_APP_SECRET`. If the digest doesn't match → HTTP 403, message dropped.

**Contract at this point:** Raw bytes verified as authentic.

### Step 3 — Payload routing

`ingress/webhook.py` checks `payload["object"] == "whatsapp_business_account"`. Anything else → HTTP 200 silently ignored (Meta sends other event types).

### Step 4 — Background scheduling

`WhatsAppReceiver.handle_payload()` iterates message entries. For each:
1. `InMemoryDeduplicationStore.try_claim(message_id)` — if already seen → skip. TTL = 24 hours. **Note: In-memory only — loses state on restart.**
2. If new → `asyncio.create_task(_process_message(context))` — immediately returns HTTP 200 to Meta.

**Contract:** Meta gets a response within milliseconds regardless of processing time.

### Step 5 — Media download (if needed)

For image/voice messages, `MetaMediaDownloader.download(media_id)` fetches the binary from Meta's CDN using the `WHATSAPP_ACCESS_TOKEN`. Returns a `DownloadedMedia` with local path, MIME type, SHA256, and size.

**Contract at this point:** Binary media on local disk.

### Step 6 — Object storage upload

`upload_downloaded_media()` reads the file bytes and calls `FakeObjectStorage.put_object(key, data)`. Produces a `MediaReference(object_key, mime_type, size_bytes)`.

**Note:** `FakeObjectStorage` is in-memory. All media is lost on process restart. This is a known gap — R2 adapter not yet wired.

### Step 7 — Normalization

`MessageNormalizer.normalize()` converts the Meta JSON structure into a `NormalizedMessage.v1`:
- `message_id` ← `message["id"]`
- `correlation_id` ← auto-generated (`cor_` prefix UUID)
- `channel` = `"whatsapp"`
- `sender` = `SenderInfo(wa_id, profile_name)`
- `timestamp` ← Unix epoch → UTC datetime
- `modality` ← `text`→`TEXT`, `audio.voice`→`VOICE`, `image`→`IMAGE`
- `text` ← body (text) or caption (image)
- `media` ← `MediaReference` (if applicable)
- `reply_context` ← `ReplyContext(replied_to_message_id)` (if a reply)

**Note:** There is a Postgres query at this point inside `receiver._process_message()` that enriches `sender.profile_name` and sets `metadata["user_role"]`. This is a boundary violation that should be removed. The identity gate handles this properly.

**Contract produced:** `NormalizedMessage.v1`

### Step 8 — Identity gate (M4)

`resolve_sender(actor_reader, wa_id)` calls `PostgresActorReader.resolve_by_whatsapp_id(wa_id)`. This executes a SQL query joining `users`, `organizations`, `external_identities` (or equivalent), returning `ActorIdentity`.

Three gate conditions. Any failure sends a canned WhatsApp reply and stops:

| Condition | Reply |
|---|---|
| `actor_identity is None` | "This number isn't registered on Mesiri..." |
| `actor_identity.organization_id is None` | "You're not part of any organization..." |
| `not actor_identity.org_active` | "Your organization's account is not active..." |

If the gate passes, `ActorIdentity` contains: `user_id`, `full_name`, `role`, `organization_id`, `org_name`, `org_active`, `projects[]`, `sites[]`.

**Contract at this point:** Sender is a verified, active, org-affiliated Mesiri user.

### Step 9 — Understanding pipeline (M3)

`UnderstandingPipeline.understand(message)`:

```
TEXT message:
  extraction.extract(message.text) → ExtractionResult
  → UnderstandingResult(semantic_type, candidates, confidence)

VOICE message:
  storage.get_object(media.object_key) → audio bytes
  speech.transcribe(audio) → SpeechResult(transcript, language, translation)
  extraction.extract(transcript) → ExtractionResult
  → UnderstandingResult(transcript, translated_text, semantic_type, candidates, confidence)

IMAGE message:
  storage.get_object(media.object_key) → image bytes
  vision.analyze_image(image) → VisionResult(classification, description)
  extraction.extract(description) → ExtractionResult
  → UnderstandingResult(document_classification, semantic_type, candidates, confidence)
```

Provider failures are caught as `MesiriError` → result is `UNUSABLE` (never raised to caller).

Confidence: `ConfidencePolicy.evaluate(signals)` → `HIGH / MEDIUM / LOW / UNUSABLE`

**Contract produced:** `UnderstandingResult.v1`

### Step 10 — Context resolution (contract layer)

`ContractContextResolver.resolve(message, understanding)`:
- All three ports (`FakeIdentityLookupPort`, `FakeScopeLookupPort`, `FakeWorkflowStateReadPort`) are empty in-memory stores
- Actor is always `unknown`, scope always `unresolved`, confidence always `LOW`
- Result is produced but currently unused

If `WHATSAPP_CONTEXT_DEBUG=true`: `log_resolved_context()` writes actor/org/project/site/role/confidence to the logger.

**Contract produced:** `ResolvedContext` (contract version — `mesiri_contracts.context.resolved_context`)

### Step 11 — Reply

`format_reply(understanding)` builds a WhatsApp-formatted text from `UnderstandingResult`:
```
*Mesiri — understood your message*

🗣 Transcript: <if voice>
🌐 Translation: <if translated>
📄 Document: <if image classified>
🏷 Type: material_update
📋 Details:
   • material_name: cement
   • quantity: 20
   • unit: bags
❓ Missing: <if any>
✅ Confidence: high
```

`WhatsAppSender.send_text(wa_id, text)` sends via `POST graph.facebook.com/v21.0/{phone_number_id}/messages`.

**The reply is driven entirely by `UnderstandingResult`. Context has no effect on the current reply.**

---

## 7. Current Architecture Status

### Ingress (M2)
- **Status:** Implemented — 100%
- **What works:** Signature verification, deduplication, normalization, media download/upload, webhook routing
- **Technical debt:** Inline SQL in `receiver._process_message()` violates the boundary. `FakeObjectStorage` means media is lost on restart.
- **Next:** Replace `FakeObjectStorage` with real R2 adapter. Remove inline SQL from receiver.

### Understanding (M3)
- **Status:** Implemented — 100%
- **What works:** Text, voice, image pipelines. Sarvam STT. Gemini/DeepSeek extraction. Gemini vision. Confidence policy. Provider failure handling.
- **Next:** None required before Planner. Provider selection will eventually move to `platform/ai/core/router.py`.

### Context (M4)
- **Status:** Partial — 65%
- **What works:** M4 `ContextResolver` with all Postgres/Redis adapters — **fully implemented and tested** but not called in production. `ContractContextResolver` called in production but with fake adapters only. Identity gate works correctly.
- **Critical gap:** Two `ResolvedContext` schemas. The M4 `ContextResolver` (`resolver.py`) must be wired into `_on_normalized` before Planner can start. `ContractContextResolver` must be retired or kept as a testing tool only.
- **Next:** Unify `ResolvedContext` schema (M4 schema is canonical). Wire M4 `ContextResolver`. Retire fake adapters from production.

### Planner (M5)
- **Status:** Not implemented — 0%
- All files are 0 bytes. Contract `PlannerDecision` is 0 bytes.
- **Requires:** Unified `ResolvedContext` + `PlannerDecision` contract.

### Workflow Runtime (M6)
- **Status:** Not implemented — 0%
- Folder structure declared, all files empty. LangGraph not installed.
- **Requires:** Planner, `WorkflowState` contract, `DraftAction` contract, Memory for checkpointing.

### Interaction (M7)
- **Status:** Not implemented — 0%
- 6 files, all 0 bytes. Contract `InteractionSpec` is 0 bytes.
- **Requires:** Workflow Runtime output.

### Memory (M8)
- **Status:** Not implemented — 0%
- Both `src/memory/` and `platform/memory/` are entirely empty.
- **Requires:** Conversation history is a Planner prerequisite.

### Rules
- **Status:** Not implemented — 0%
- Contract `rules/result.py` is 0 bytes.

### Tools
- **Status:** Not implemented — 0%
- Contract `tools/` files are all 0 bytes.

### Authorization
- **Status:** Implemented at identity gate — field-level RBAC not yet enforced
- `ActorIdentity` carries `role` string. Permissions are in the M4 `ContextResolver` output (`role_ids`, `permissions`) but Context is not wired, so permissions are not flowing.

### Rendering
- **Status:** Implemented as M3-based plain text
- `format_reply(UnderstandingResult)` only. Future: rich WhatsApp templates, confirmation cards, correction flows via `channel/` module.

---

## 8. Contracts

Every shared contract consumed or produced by this folder lives in `shared/contracts/src/mesiri_contracts/`.

### `NormalizedMessage.v1`
- **File:** `assistant/normalized_message.py`
- **Producer:** M2 ingress (`normalization.py`)
- **Consumer:** M3 understanding pipeline, M4 context resolver, identity gate
- **Why it exists:** Decouples Meta's proprietary webhook JSON from all downstream logic. If Meta changes their API, only `normalization.py` changes.
- **Key fields:** `message_id`, `correlation_id`, `channel`, `sender.wa_id`, `modality`, `text`, `media`, `reply_context`
- **Status:** Frozen. Do not modify without cross-review.

### `UnderstandingResult.v1`
- **File:** `assistant/understanding_result.py`
- **Producer:** M3 understanding pipeline
- **Consumer:** Context resolver, reply formatter, future Planner
- **Why it exists:** Decouples AI output from downstream business logic. The pipeline may use different providers; the result shape stays constant.
- **Key fields:** `semantic_type`, `candidates`, `overall_confidence`, `transcript`, `translated_text`, `document_classification`, `missing_fields`
- **Status:** Frozen. Do not modify without cross-review.

### `ResolvedContext` (M4 version)
- **File:** `assistant/resolved_context.py`
- **Producer:** M4 `ContextResolver` (`context/resolver.py`)
- **Consumer:** Future Planner
- **Why it exists:** Gives the Planner a single authoritative answer to "who is this, where are they, what can they do?"
- **Key fields:** `organization_id`, `user_id`, `role_ids`, `permissions`, `project_id`, `site_id`, `context_source`, `context_confidence`
- **Status:** Implemented, not yet wired to production path. **This should become the canonical `ResolvedContext`.**

### `ResolvedContext` (contract version)
- **File:** `context/resolved_context.py`
- **Producer:** `ContractContextResolver` (`context/contract_resolver.py`)
- **Consumer:** `runtime/inbound_journey.py`
- **Why it exists:** Designed as a simpler port-contract version during Phase 1–3 development. Currently used in production path with fake adapters only.
- **Key fields:** `actor` (ActorContext), `scope` (ScopeContext), `workflow`, `interaction`, `reply`, `confidence`, `ambiguities`, `warnings`
- **Status:** Will be retired or merged into the M4 version once Context is unified.

### `ActorIdentity`
- **File:** `backend/ports.py` (inside this folder, not shared)
- **Producer:** `PostgresActorReader`
- **Consumer:** `live_identity.py`, `_on_normalized()` in `dependencies.py`
- **Why it exists:** The backend capability boundary. Gives the assistant just enough identity information without exposing DB schema.
- **Status:** Stable.

### `PlannerDecision`
- **File:** `assistant/planner_decision.py`
- **Status:** **0 bytes — not defined.**

### `CanonicalEvent`, `WorkflowState`, `DraftAction`, `InteractionSpec`
- All 0 bytes — not defined.

---

## 9. Ports and Adapters

### Philosophy

Every external dependency (AI provider, database, cache, object storage, channel) is hidden behind a Python `Protocol`. The assistant core logic depends only on the protocol. Concrete adapters are injected at startup time in `build_container()`. Tests inject fake adapters.

This means:
- The assistant can be tested entirely without network calls, databases, or API keys
- Providers can be swapped without touching business logic
- Fake adapters document the expected contract of real adapters

### Ports and their adapters

| Port | Defined in | Fake | Production |
|---|---|---|---|
| `SpeechUnderstandingProvider` | `platform/ai/ports/speech.py` | `FakeSpeechProvider` | `SarvamSpeechProvider` |
| `VisionUnderstandingProvider` | `platform/ai/ports/vision.py` | `FakeVisionProvider` | `GeminiProvider` |
| `StructuredExtractionProvider` | `platform/ai/ports/extraction.py` | `FakeExtractionProvider` | `GeminiProvider`, `DeepSeekExtractionProvider` |
| `ObjectStoragePort` | `mesiri_contracts/common/storage.py` | `FakeObjectStorage` | ⚠️ No real adapter wired |
| `ActorReader` | `backend/ports.py` | ⚠️ None | `PostgresActorReader` |
| `DeduplicationStore` | `ingress/deduplication.py` | `InMemoryDeduplicationStore` | ⚠️ No Redis adapter |
| `IdentityLookupPort` (contract) | `mesiri_contracts/context/ports.py` | `FakeIdentityLookupPort` | ⚠️ None |
| `ScopeLookupPort` (contract) | `mesiri_contracts/context/ports.py` | `FakeScopeLookupPort` | ⚠️ None |
| `WorkflowStateReadPort` (contract) | `mesiri_contracts/context/ports.py` | `FakeWorkflowStateReadPort` | ⚠️ None |
| `ExternalIdentityRepository` (M4) | `context/ports.py` | `FakeExternalIdentityRepository` | `PostgresExternalIdentityRepository` |
| `ProjectRepository` (M4) | `context/ports.py` | `FakeProjectRepository` | `PostgresProjectRepository` |
| `SiteRepository` (M4) | `context/ports.py` | `FakeSiteRepository` | `PostgresSiteRepository` |
| `ActiveContextStore` (M4) | `context/ports.py` | `FakeActiveContextStore` | `RedisActiveContextStore` |

**Missing real adapters (⚠️):**
- Object storage real adapter (R2/S3) — media lost on restart
- Redis deduplication adapter — duplicate messages allowed on restart
- `IdentityLookupPort` / `ScopeLookupPort` real adapters — needed to retire fake context resolvers

---

## 10. Dependency Rules

### Allowed imports from within `src/`

| From | May import from |
|---|---|
| `ingress/` | `mesiri_contracts.assistant.*`, `mesiri_contracts.common.*` |
| `understanding/` | `mesiri_ai.ports.*`, `mesiri_contracts.assistant.*`, `mesiri_contracts.common.*` |
| `context/` | `mesiri_contracts.assistant.*`, `mesiri_contracts.context.*`, `mesiri_contracts.common.*`, `backend.ports` |
| `backend/postgres/` | `mesiri.*` (backend infrastructure) — this is the only file with this permission |
| `runtime/` | All modules in `src/` (it is the wiring layer) |
| `channel/` | `mesiri_contracts.*` |
| Any module | `mesiri_contracts.*`, `mesiri_ai.ports.*` |

### Prohibited imports

| From | Must NOT import |
|---|---|
| `ingress/` | `context/`, `understanding/`, `backend/postgres/`, `mesiri.*` |
| `understanding/` | `context/`, `ingress/`, `mesiri.*` (except via ports) |
| `context/` (except `postgres_repositories.py`) | `mesiri.infrastructure.*`, table names, ORM models |
| Any module | AI provider SDKs directly (`google.generativeai`, `anthropic`, `openai`) |
| Any module (except `backend/postgres/`) | `sqlalchemy`, raw SQL, `asyncpg` |
| Any module | Contracts defined inside `apps/whatsapp-assistant/src/` (use `shared/contracts/`) |

### Dependency direction

```
runtime/ (wiring)
    ↓ depends on
ingress/ → understanding/ → context/ → planner/ → workflows/ → interactions/
    ↓                ↓           ↓
backend/        mesiri_ai/    mesiri_contracts/
(ports only)    (ports only)  (shared contracts)
```

**Rule: dependencies flow downward only.** Ingress must not know about context. Context must not know about workflows. Each layer is ignorant of layers above it.

---

## 11. Design Principles

### Contracts First

Every module boundary is defined by a Pydantic model in `shared/contracts/`. No module may depend on the internal data structures of another module. If two modules need to share data, a contract must exist first.

**Why:** Without contracts, modules become entangled. A change to `UnderstandingResult` would cascade through ingress, context, and planner simultaneously. Contracts make those cascades explicit and reviewable.

### Ports and Adapters

All I/O (database, cache, AI providers, object storage, external HTTP) is hidden behind Python `Protocol` interfaces. Business logic depends only on protocols. Adapters implement protocols.

**Why:** Enables testing without infrastructure. Enables swapping providers without touching business logic. Enables fake adapters that are behaviorally equivalent to real ones — making unit tests trustworthy.

### Dependency Injection at the Boundary

`build_container()` in `runtime/dependencies.py` is the only place where concrete implementations are selected and wired together. No module constructs its own dependencies. All dependencies flow in from outside.

**Why:** If a module creates its own database connection, it cannot be tested in isolation. DI makes substitution trivial and makes the dependency graph explicit.

### AI Provider Isolation

The assistant never imports a provider SDK. It imports from `mesiri_ai.ports.*`. The gateway in `platform/ai/` owns SDK imports, retry logic, model selection, and fallback.

**Why:** AI providers change constantly. Models are deprecated, APIs shift, pricing changes. Isolating all SDK contact in `platform/ai/` means provider migrations require touching exactly one adapter file.

### Single Responsibility per Module

Each module does exactly one thing:
- `ingress/` normalizes raw webhooks
- `understanding/` interprets content semantically
- `context/` resolves business scope
- `planner/` decides what action to take (future)
- `workflows/` executes the action (future)

**Why:** When something breaks, the boundaries tell you exactly where to look.

### Stateless Processing

Each inbound message is processed independently. There is no in-memory message state shared between invocations. Conversation state (future) will be stored externally in Redis/PostgreSQL and loaded per-request.

**Why:** Stateless processing enables horizontal scaling and eliminates a class of race conditions.

### Business Logic Separation

The assistant is a routing and orchestration layer. It must not contain domain rules. "A material receipt requires a quantity > 0" is a domain rule. It belongs in the material domain service, not in a LangGraph node or a context policy.

**Why:** Domain rules change with the business. If they are scattered across workflow nodes and LangGraph graphs, finding and changing them becomes a dangerous grep exercise.

### Human-in-the-Loop (future)

The architecture reserves the Interaction layer (M7) for cases where the AI is not confident enough to commit data automatically. A workflow may decide to ask the user for confirmation before calling the application layer. The user's response routes back through the ingress and is matched to the pending interaction.

**Why:** In construction, errors are expensive. An AI that silently records wrong quantities is worse than one that asks. The confirmation loop is a first-class architectural concern, not an afterthought.

### Correlation ID Propagation

Every `NormalizedMessage` carries a `correlation_id` generated at ingress. Every downstream step — understanding, context, workflow, application call — must carry and log the same `correlation_id`. It must never be replaced or regenerated mid-journey.

**Why:** Without correlation IDs, debugging a failed message requires reconstructing its journey from timestamps and wa_ids. With them, one `grep` produces the complete trace.

---

## 12. Common Mistakes

This section is written for AI coding agents. These are the most frequent patterns that violate the architecture.

---

### Mistake 1: Writing SQL inside the assistant

```python
# WRONG — SQL in context/resolver.py
from sqlalchemy import text
result = await conn.execute(text("SELECT id FROM users WHERE whatsapp_number = :n"), {"n": wa_id})

# CORRECT
actor = await self._actor_reader.resolve_by_whatsapp_id(wa_id)
```

**Why it's wrong:** Schema knowledge belongs in `backend/postgres/actor.py`. If the `whatsapp_number` column is renamed, every SQL statement in the assistant breaks. With the port, only `actor.py` breaks.

---

### Mistake 2: Importing SQLAlchemy, bcrypt, or ORM models outside `backend/postgres/`

```python
# WRONG — in understanding/pipeline.py
from mesiri.infrastructure.postgres.models.user import User

# CORRECT — never needed in understanding/
```

**Why it's wrong:** The understanding pipeline does not need to know about users at all. If an agent finds itself needing user data inside the understanding pipeline, the design is wrong.

---

### Mistake 3: Creating a new contract inside the assistant

```python
# WRONG — apps/whatsapp-assistant/src/my_module/events.py
class ReceiptCreatedEvent(BaseModel):
    receipt_id: str

# CORRECT — shared/contracts/src/mesiri_contracts/events/receipt.py
class ReceiptCreatedEvent(BaseModel):
    receipt_id: str
```

**Why it's wrong:** A contract defined inside the assistant can only be consumed by the assistant. It is not a contract — it is an internal data class. Real contracts belong in `shared/contracts/` so producer and consumer can both import from the same canonical location.

---

### Mistake 4: Calling an AI provider SDK directly

```python
# WRONG — in context/resolver.py
import google.generativeai as genai
model = genai.GenerativeModel("gemini-2.5-flash")
response = model.generate_content("Classify this project name")

# CORRECT
result = await self._extraction.extract(text, correlation_id=correlation_id)
```

**Why it's wrong:** Bypasses retry logic in `platform/ai/core/retry.py`, model routing in `core/router.py`, and makes context resolution dependent on a live API key. Context resolution should work with fake providers in tests.

---

### Mistake 5: Resolving context inside the understanding pipeline

```python
# WRONG — understanding/pipeline.py accessing the context
from context.resolver import ContextResolver
actor = await ContextResolver(...).resolve(...)

# CORRECT — context resolution is a separate stage in inbound_journey.py
understanding = await pipeline.understand(message)
resolved = await context_resolver.resolve(message, understanding)
```

**Why it's wrong:** Understanding must not depend on context. Understanding is the semantic interpretation of the raw message. Context is the business scoping. They are separate stages with a clean contract between them.

---

### Mistake 6: Putting business validation in a LangGraph node

```python
# WRONG — workflows/material_usage/nodes.py
def validate_quantity(state):
    if state["quantity"] <= 0:
        raise ValueError("Invalid quantity")  # business rule in workflow

# CORRECT — validate in the domain service call
await material_service.record_receipt(CreateReceiptCommand(...))
# The service raises a domain exception; the workflow catches and routes
```

**Why it's wrong:** Business rules belong to the domain. If the rule changes (e.g. "quantity must not exceed project budget"), you'd need to change the workflow node. The domain service is the single source of truth for business rules.

---

### Mistake 7: Using `message.metadata["user_role"]` as authorization

```python
# WRONG — using metadata for authorization
if message.metadata.get("user_role") == "site_engineer":
    ...

# CORRECT — use the resolved ActorIdentity from the identity gate
if actor.role == "site_engineer":
    ...
```

**Why it's wrong:** `metadata["user_role"]` is populated by an inline Postgres query inside `receiver._process_message()` — a boundary violation that may be removed. The authoritative role comes from `ActorIdentity` resolved through `PostgresActorReader`.

---

### Mistake 8: Generating a new correlation_id mid-journey

```python
# WRONG — minting a new correlation ID in context resolver
import uuid
correlation_id = str(uuid.uuid4())

# CORRECT — propagate the one from the message
correlation_id = message.correlation_id
```

**Why it's wrong:** The correlation ID was minted at ingress. Every log line, every port call, every downstream service should emit the same `correlation_id`. Creating a new one severs the trace chain.

---

### Mistake 9: Adding state to `_on_normalized` via closure capture

```python
# WRONG — storing per-message state in a closure variable
message_count = 0  # shared mutable state across messages
async def _on_normalized(message):
    nonlocal message_count
    message_count += 1
```

**Why it's wrong:** `_on_normalized` may run concurrently for multiple messages. Shared mutable state in closures causes race conditions. Message-scoped state must be local to each invocation.

---

## 13. Development Checklist

Before creating or modifying any module in this folder:

### Architecture

- [ ] Does this module have a clear, single responsibility?
- [ ] Is the responsibility in the list of things this folder owns (§3)?
- [ ] Does this module introduce a new layer dependency that goes against the dependency direction (§10)?
- [ ] Does this touch M2 or M3 without explicit cross-review from both Alan and Ilan?

### Contracts

- [ ] If this module produces data consumed by another module, is there a shared contract in `shared/contracts/`?
- [ ] Are you importing contracts from `mesiri_contracts.*`? (Not defining them inside the assistant.)
- [ ] Did you check that the contract you need doesn't already exist (check all files in `shared/contracts/src/mesiri_contracts/`)?

### Ports & Adapters

- [ ] Does this module need I/O? (database, AI, cache, HTTP) → Is it behind a port?
- [ ] Is there a fake adapter for the port so unit tests can run without infrastructure?
- [ ] Is the fake adapter's behavior equivalent to the real adapter's contract?

### Tests

- [ ] Unit tests use only fake adapters — no live database, no API keys, no HTTP calls
- [ ] Contract tests verify the module's output validates against the shared contract
- [ ] Integration tests are marked `@pytest.mark.integration` and skipped by default

### Boundaries

- [ ] No SQL outside `backend/postgres/actor.py`
- [ ] No AI SDK imports outside `platform/ai/adapters/`
- [ ] No imports of `mesiri.infrastructure.*` outside `backend/postgres/actor.py`
- [ ] No contracts defined inside `apps/whatsapp-assistant/src/`
- [ ] No business rules in workflow nodes, pipeline steps, or context policy

### Dependency Injection

- [ ] Does the module accept all external dependencies as constructor arguments?
- [ ] Are dependencies registered in `build_container()` in `runtime/dependencies.py`?
- [ ] Can the module be instantiated in a test with fake dependencies, without any environment variables?

### Correlation

- [ ] Does every log statement include `correlation_id`?
- [ ] Is `correlation_id` propagated from the input message — never regenerated?

---

## 14. Future Roadmap

This section describes how this folder is expected to evolve, based on the current codebase state and declared-but-empty module structure.

### Current (implemented)

- M2 ingress pipeline (webhook → `NormalizedMessage`)
- M3 understanding pipeline (speech, vision, extraction, confidence)
- M4 identity gate (Postgres-backed, gates unregistered/suspended users)
- M4 context resolution adapters (Postgres + Redis, not yet wired to production path)
- HTTP control-plane APIs (auth, users, projects, admin)
- WhatsApp reply (M3-based understanding summary)

### Near Future (required before Planner)

1. **Unify `ResolvedContext`** — retire `mesiri_contracts.context.resolved_context` and `ContractContextResolver`. The M4 `ContextResolver` with `mesiri_contracts.assistant.resolved_context.ResolvedContext` becomes the single canonical output.

2. **Wire M4 `ContextResolver`** — replace `ContractContextResolver` (fake adapters) with `ContextResolver` (real Postgres/Redis adapters) in `_on_normalized`. The identity gate result (`ActorIdentity`) should seed the resolver to avoid a second DB round-trip.

3. **Add `ActorReader` fake** — `PostgresActorReader` has no fake. Tests that need an unregistered user or a suspended org currently require a live database. A `FakeActorReader` is needed for identity gate testing.

4. **Define `PlannerDecision` contract** — `shared/contracts/src/mesiri_contracts/assistant/planner_decision.py` is 0 bytes. This must be defined (with Alan + Ilan review) before Planner can be implemented.

5. **Implement minimum Memory** — at minimum, a conversation turn history store so the Planner knows the previous message's semantic type and project context.

### Medium Term (Planner + Workflows)

6. **Implement Planner** — `planner/planner.py`. Receives `ResolvedContext` + `UnderstandingResult`, decides: start workflow / continue workflow / clarify / reply directly. Produces `PlannerDecision`.

7. **Implement first LangGraph workflow** — `workflows/material_usage/`. Expense capture exists as an empty scaffold. Material usage is the primary INT-001 proof. Requires `WorkflowState` contract, `DraftAction` contract, `CanonicalEvent` contract.

8. **Implement Interaction layer** — `interactions/`. Confirmation requests, field corrections. Requires Planner output.

9. **Replace `FakeObjectStorage`** — wire the real R2 (Cloudflare) or S3 adapter so voice/image media survives process restart.

### Long Term

10. **Memory** — `platform/memory/` is entirely empty. Semantic memory (pgvector + Voyage embeddings) enables the Planner to recall prior conversations, detect recurring patterns, and provide context-aware replies.

11. **Rules Engine** — `shared/contracts/src/mesiri_contracts/rules/` is empty. Business rules (approval thresholds, quantity limits) should be externalized from domain services into a configurable rules store.

12. **Tool Executor** — `shared/contracts/src/mesiri_contracts/tools/` is empty. Enables workflows to call external services (weather, material price APIs, ERP) through a controlled, auditable tool interface.

13. **Timeline** — The mobile app has a `timeline.tsx` stub. The backend has no timeline table. A structured event log (CanonicalEvent → timeline) enables project managers to see a chronological record of field reports.

---

## 15. Glossary

### Contract
A Pydantic `BaseModel` defined in `shared/contracts/` that describes the data exchanged between two modules. The producer is responsible for producing valid instances. The consumer may only depend on the fields defined in the contract. Contracts are versioned (`v1`, `v2`) and changes require cross-team review. Example: `NormalizedMessage.v1`.

### Port
A Python `Protocol` class that defines the interface of an external dependency (database, AI provider, cache). The assistant depends on the protocol, never on the concrete implementation. Example: `StructuredExtractionProvider`.

### Adapter
A concrete class that implements a Port protocol. Adapters come in two kinds: **fake** (in-memory, deterministic, for testing) and **production** (real SDK calls, real network). Example: `GeminiProvider` implements `StructuredExtractionProvider`.

### Resolver
A class that takes an input (typically `NormalizedMessage` + `UnderstandingResult`) and produces a richer output by querying ports. The Context Resolver produces `ResolvedContext`. Resolvers are read-only — they never write data.

### Workflow
A stateful, multi-step process that collects business data from a user over one or more conversation turns. Implemented using LangGraph. Example: the material usage workflow asks "what quantity?" if missing, then asks "which project?" if ambiguous, then calls the domain service to record the receipt.

### Application Layer
The layer that translates workflow output (`DraftAction`) into domain service calls. It knows about domain services and command models. It does not know about WhatsApp, LangGraph, or AI providers.

### Domain
The business entities and rules. In Mesiri: material receipts, expenses, equipment usage records, labour reports. Domain services validate business invariants and persist records. The domain is owned by the backend — the assistant never accesses it directly.

### Canonical Event
A domain event produced when a workflow commits data. Example: `MaterialReceiptCreated`. Canonical events flow from the application layer to the event bus and are eventually consumed by the timeline and reporting modules.

### Planner
The decision-maker between context resolution and workflow execution. Given a `ResolvedContext` and `UnderstandingResult`, it decides: which workflow to start, which workflow is already in progress and should continue, whether the message is ambiguous and needs clarification, or whether to reply directly without a workflow.

### Interaction
A human-in-the-loop step where the assistant asks the user for confirmation, a missing field, or a correction before committing data. The user's response is a new inbound message that the ingress routes to the pending interaction rather than starting a new journey.

### Checkpoint
A snapshot of a workflow's state persisted to storage (Redis) after each step. If the process restarts, the workflow resumes from the last checkpoint rather than from the beginning. LangGraph's `Checkpointer` interface provides this.

### Context
The resolved, authoritative business scope for an inbound message: who the sender is, which organization they belong to, which project and site the message concerns, what permissions they have, and how confident the resolver is in each of those answers. Context is produced by the `ContextResolver` and consumed by the Planner.

### Workflow Runtime
The execution environment for LangGraph workflow graphs. It receives a `PlannerDecision` and runs the appropriate graph, managing state, transitions, and checkpoint persistence. It never contains business logic — that belongs in the Application Layer.

### Tool Executor
A controlled interface through which workflows can call external services. Tools are defined with input schemas and output contracts. The executor validates inputs, calls the tool, and returns the result. No workflow may call an external service except through the Tool Executor.

### Memory
A service that provides the Planner with relevant conversation history and semantic context. At minimum: the last N turns of the conversation. At full capability: semantic retrieval of prior similar messages across all time.

### Rules Engine
An externalized store of configurable business rules. Example: "material receipts exceeding 500 bags require manager approval." Rules are evaluated by the Application Layer before committing data. Externalizing rules means changing them does not require code deployment.

### Identity Gate
The first check after ingress normalization: is this WhatsApp number registered? Are they part of an active organization? If not, the journey ends immediately with a canned user-facing message. No AI compute is spent on unregistered users.

### Correlation ID
A UUID string generated at ingress (`cor_` prefix) that uniquely identifies one inbound message's journey through the system. Every log statement, every port call, every downstream service call must carry this ID. It enables end-to-end tracing of any message from webhook to reply.

---

*This document reflects the codebase at commit `48074ce` — July 2026. Update it whenever the architecture changes.*
