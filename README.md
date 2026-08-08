# Mesiri.ai Engineering Foundation

Monorepo for Mesiri.ai - AI-powered construction operations platform.

## Structure
- `apps/`: Deployable applications (Control Panel, Dashboard, Mobile, Desktop, Marketing)
- `services/`: Backend services (API, AI Workers, WhatsApp, etc.)
- `packages/`: Shared libraries (UI, Auth, Database, etc.)
- `infrastructure/`: DevOps & Deployment configurations
- `docs/`: Comprehensive documentation

## Quick Start (frontend / TS workspace)
1. `pnpm install`
2. `pnpm run dev`

## Python runtime (assistant: M1 infrastructure + M3 understanding)
The assistant runtime spans four Python import roots — `shared/contracts`
(`mesiri_contracts`), `platform/ai` (`mesiri_ai`), `backend` (`mesiri`), and
`apps/whatsapp-assistant`.

```bash
uv venv --python 3.11
uv pip install -e ".[dev]"      # + [infra] for docker/live, [providers] for AI SDKs
cp .env.example .env

make dev            # start local Postgres + Redis (docker)
make migrate        # apply infrastructure migrations
make test           # full suite against fakes — no docker, no external APIs
make m1-golden      # M1 "Infrastructure Alive" golden-scenario proof
```

Health endpoints: `uvicorn --factory mesiri.http.app:create_app` →
`/health/live`, `/health/ready`.
