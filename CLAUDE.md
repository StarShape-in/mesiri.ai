# MERCON — Rules for AI Agents

Read this before changing anything. These are owner-set rules. If a task
conflicts with them, stop and ask the owner — do not improvise.

## Rule 0: Analyze before you change

Read the existing code, schema, and docs relevant to your task **before**
editing. Do not invent features, fields, enum values, pages, or roles that
are not already in the codebase or explicitly requested by the owner.

## Rule 0.5: Keep PROGRESS.md in sync

`PROGRESS.md` (repo root) is the single source of truth for "where is the
project." Whenever you change code, schema, an endpoint, or wire a screen — or
finish a step — **update `PROGRESS.md` in the same change**: flip the ⬜/🔄/✅
marker, move the row between Completed and Next, bump `Last updated`, and adjust
the TL;DR % if an area crossed a threshold. Never mark ✅ from intent alone —
verify against code. This lets the owner ask "where are we?" and get a correct
answer without re-reading the codebase.

## Roles — EXACTLY THREE, never add more

There are exactly **3 user roles**: `Admin`, `Operator`, `Driver`.

- Never add, rename, or remove a role without the owner explicitly asking.
- (History: an agent once added Dispatcher/Accountant/Viewer unprompted.
  They were removed. Do not reintroduce them.)

Sources of truth, which must always stay in sync:

| Location | What |
|---|---|
| `backend/api-server/prisma/schema.prisma` → `enum Role` | Database enum (canonical) |
| `packages/shared-types/src/index.ts` → `UserRole` | Shared TS type — must mirror the Prisma enum |

Never hardcode role lists in UI components beyond these three; import types
from `@mercon/shared-types`.

## Who uses which app

| App | Used by | Notes |
|---|---|---|
| Web dashboard (`frontend/web-dashboard`) | **Admin, Operator** | Drivers never log in here |
| Mobile app (`frontend/mobile-app/mercon-app`) | **Operator, Driver** | Drivers log in via license number (`mobileAuthController`) |
| User Management page (`/settings/users`) | **Admin, Operator** | Gated by `RequireRole` + `authorizeRoles('Admin', 'Operator')`; also lists Drivers (read-only) alongside Admin/Operator so it's a full "all platform users" view — but Driver rows cannot be created/edited/deleted here, only viewed. Web-user create/edit (`createUserBody`/`updateUserBody`) still only accepts role `Admin`/`Operator` — Driver-role Users are still not creatable through this page's form |

Driver accounts/access (creation, edit, documents) are managed through the
Drivers module (`/drivers`), not through the User Management form. The
User Management page links out to "Add Driver" (`/drivers/new`) rather than
creating drivers itself.

## Database & seed rules

- Default users (created by `backend/api-server/prisma/seed.ts`):
  `admin` (role Admin) and `operator` (role Operator).
- The seed runs on **every** container start — it must stay **idempotent**
  (upserts, never blind creates) and must **never overwrite passwords** of
  existing users.
- Do not modify `schema.prisma` unless the task explicitly requires it. The
  production container runs `prisma db push --accept-data-loss` on start, so
  schema changes hit the live database automatically — treat them as
  production changes.
- Never seed fake/demo data (drivers, trips, customers, invoices). This was
  deliberately removed.

## Deployment (production = mercon.tech)

- Pushing to `main` triggers `.github/workflows/ci-cd.yml` on a self-hosted
  runner: it force-removes the containers and runs `docker-compose up -d
  --build` from the repo root.
- Postgres data persists in the `pgdata` volume — deploys do NOT reset the
  database. Fixing bad data requires the seed (idempotent upserts) or manual
  SQL, not a redeploy.
- Nginx on the VPS routes `mercon.tech/api/*` → API (port 3050) and
  everything else → web dashboard (port 3060).
- The repo is npm workspaces; Docker builds use the **repo root** as build
  context. Shared types must build first (`npm run build:types`).
- **Never add `prepare`/`install` lifecycle scripts to workspace packages.**
  The Docker images copy only `package.json` manifests before `npm install`
  (for layer caching), and npm runs workspace `prepare` scripts during
  install even with `--ignore-scripts` — with no sources present the script
  fails and the whole deploy breaks (this happened; see git history).
  Builds are invoked explicitly in the Dockerfiles instead.

## General conduct

- Local ≠ production: local Postgres (port 5432) and hosted Postgres are
  different databases. When debugging "works locally, broken on hosted",
  compare **data** first, then deployed code version.
- Before claiming something is fixed, verify it (run the seed, hit the API,
  build the workspace).
- Don't commit build artifacts (`dist/`, `*.tsbuildinfo`) or the old
  `mercon-api-deploy.tar.gz` flow — deployment is git-push based now.
- When adding any role-gated feature, enforce it in **both** places: backend
  route middleware (`authorizeRoles(...)`) and frontend (`RequireRole` /
  conditional nav). Frontend-only gating is not security.
