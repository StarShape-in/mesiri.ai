# Deployment Guide

This project uses GitHub Actions for automated CI/CD. Every push to `main` that passes tests is automatically deployed to the VPS at `mercon.tech`.

## How it works

```
git push → main
    ↓
GitHub Actions: deploy.yml
    ├── Unit tests (Python, fakes only)
    ├── Build control-panel (Vite)
    └── Deploy (only if both above pass)
            ├── SSH → git pull origin/main
            ├── uv pip install (Python deps)
            ├── alembic upgrade head (migrations)
            ├── systemctl restart mesiri
            ├── Health check /health
            └── rsync frontend dist → /var/www/mesiriadmin/
```

If migrations fail or the health check fails after restart, the deploy step exits with a non-zero code and GitHub marks the deployment as failed. The service is restarted again as a best-effort rollback.

---

## First-time VPS setup

This only needs to be done once (or when provisioning a new server).

### 1. Bootstrap the VPS

```bash
# Run from your local machine
ssh root@187.127.180.98 'bash -s' < scripts/setup_vps.sh
```

This will:
- Clone the repo to `/opt/mesiri`
- Create a Python venv at `/opt/mesiri/.venv`
- Install Python dependencies
- Install and enable the `mesiri` systemd service
- Create `/var/www/mesiriadmin/` for the frontend

### 2. Create the production `.env`

```bash
ssh root@187.127.180.98
cp /opt/mesiri/.env.example /opt/mesiri/.env
nano /opt/mesiri/.env
```

Fill in:
- `MESIRI_POSTGRES__HOST`, `MESIRI_POSTGRES__PASSWORD`, etc.
- `MESIRI_REDIS__HOST`
- WhatsApp credentials
- AI provider keys (Sarvam, Gemini)
- `MESIRI_ENVIRONMENT=production`

Then start the service:
```bash
systemctl start mesiri
journalctl -u mesiri -f   # watch logs
```

### 3. Create a deploy SSH key pair

```bash
# On your local machine (or on the VPS — either works)
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_deploy -N ""
```

Add the **public key** to the VPS:
```bash
ssh root@187.127.180.98 "echo '$(cat ~/.ssh/github_deploy.pub)' >> ~/.ssh/authorized_keys"
```

### 4. Add GitHub Secrets

Go to: **Repo → Settings → Secrets and variables → Actions → New repository secret**

| Secret name | Value |
|---|---|
| `VPS_SSH_KEY` | Contents of `~/.ssh/github_deploy` (the private key) |
| `VPS_HOST` | `187.127.180.98` |
| `VPS_USER` | `root` |

### 5. Create a GitHub Environment (optional but recommended)

Go to: **Repo → Settings → Environments → New environment**

Name it `production`. You can add required reviewers or deployment protection rules here so pushes to main require approval before deploying.

---

## Migrations

Migrations use **Alembic**. The migration chain lives in `backend/migrations/versions/`.

### Create a new migration

```bash
# Auto-generate from SQLAlchemy model changes
make migrate-generate MSG="add_foo_table"

# Or write it by hand in backend/migrations/versions/
```

### Apply migrations locally

```bash
make migrate
```

### Apply migrations in production (done automatically by CD)

```bash
ssh root@187.127.180.98
cd /opt/mesiri/backend
PYTHONPATH=/opt/mesiri/shared/contracts/src:/opt/mesiri/platform/ai/src:/opt/mesiri/backend/src:/opt/mesiri/apps/whatsapp-assistant/src \
  /opt/mesiri/.venv/bin/alembic upgrade head
```

### Roll back one migration

```bash
ssh root@187.127.180.98
cd /opt/mesiri/backend
PYTHONPATH=... /opt/mesiri/.venv/bin/alembic downgrade -1
```

---

## Manual emergency deploy

If you need to deploy without waiting for CI:

```bash
# Trigger the workflow manually from the GitHub Actions UI:
# Actions → Deploy to Production → Run workflow → main
```

Or directly on the VPS:

```bash
ssh root@187.127.180.98
cd /opt/mesiri
git pull origin main
.venv/bin/uv pip install -e ".[infra,providers]" --quiet
cd backend && PYTHONPATH=... .venv/bin/alembic upgrade head && cd ..
systemctl restart mesiri
```

---

## Useful commands on the VPS

```bash
# Live backend logs
journalctl -u mesiri -f

# Service status
systemctl status mesiri

# Restart backend
systemctl restart mesiri

# Check which commit is deployed
git -C /opt/mesiri log -1 --oneline

# Current migration revision
cd /opt/mesiri/backend && PYTHONPATH=... .venv/bin/alembic current
```

---

## Directory layout on the VPS

```
/opt/mesiri/                  ← git repo (main branch)
├── .venv/                    ← Python virtualenv (not in git)
├── .env                      ← production env vars (not in git)
├── backend/
│   └── migrations/           ← Alembic migrations
├── apps/whatsapp-assistant/
│   └── src/main.py           ← uvicorn entrypoint
└── infra/
    └── mesiri.service        ← systemd unit (installed to /etc/systemd)

/var/www/mesiriadmin/         ← control panel static files (served by nginx)
/etc/nginx/sites-available/mercon   ← nginx config (from mercon.conf)
/etc/systemd/system/mesiri.service  ← installed copy of infra/mesiri.service
```
