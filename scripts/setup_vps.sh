#!/usr/bin/env bash
# scripts/setup_vps.sh
#
# One-time VPS bootstrapping script.  Run this ONCE on a fresh server (or when
# migrating from the old manual-deploy approach) to switch the VPS to a
# git-pull-based deployment model.
#
# Usage (from your local machine):
#
#   ssh root@<VPS_IP> 'bash -s' < scripts/setup_vps.sh
#
# After this script succeeds:
#   • The repo lives at /opt/mesiri
#   • A Python venv with uv exists at /opt/mesiri/.venv
#   • The mesiri systemd service is enabled and running
#   • GitHub Actions can deploy via SSH using the key you add below
#
# Prerequisites on the VPS:
#   • Ubuntu 22.04 / Debian 12 (or compatible)
#   • git, nginx, certbot already installed
#   • PostgreSQL running (local or remote) with credentials ready

set -euo pipefail

REPO_URL="git@github.com:your-org/Mesiri.AI.git"   # ← update this
REPO_DIR="/opt/mesiri"
VENV_DIR="${REPO_DIR}/.venv"
SERVICE_NAME="mesiri"
FRONTEND_DIR="/var/www/mesiriadmin"

echo "════════════════════════════════════════════"
echo "  Mesiri.AI  —  VPS setup"
echo "════════════════════════════════════════════"

# ── 1. System packages ──────────────────────────────────────────────────────
echo "→ Installing system packages..."
apt-get update -q
apt-get install -y -q curl git python3.11 python3.11-venv rsync

# Install uv (fast Python package manager)
if ! command -v uv &>/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="${HOME}/.local/bin:${PATH}"
fi

# ── 2. Clone repo ───────────────────────────────────────────────────────────
echo "→ Cloning repository to ${REPO_DIR}..."
if [ -d "${REPO_DIR}/.git" ]; then
  echo "  Repo already exists — skipping clone, pulling instead."
  git -C "${REPO_DIR}" fetch --prune origin
  git -C "${REPO_DIR}" reset --hard origin/main
else
  # If old files exist from the manual-deploy era, back them up first
  if [ -d "${REPO_DIR}" ]; then
    mv "${REPO_DIR}" "${REPO_DIR}.bak.$(date +%s)"
    echo "  Backed up old /opt/mesiri to ${REPO_DIR}.bak.*"
  fi
  git clone "${REPO_URL}" "${REPO_DIR}"
fi

# ── 3. Python virtual environment ───────────────────────────────────────────
echo "→ Creating Python venv with uv..."
cd "${REPO_DIR}"
uv venv --python 3.11 "${VENV_DIR}"
"${VENV_DIR}/bin/uv" pip install -e ".[infra,providers]" --quiet

# ── 4. Production .env ──────────────────────────────────────────────────────
if [ ! -f "${REPO_DIR}/.env" ]; then
  echo ""
  echo "  ⚠  No .env file found at ${REPO_DIR}/.env"
  echo "     Copy .env.example and fill in production values:"
  echo ""
  echo "       cp ${REPO_DIR}/.env.example ${REPO_DIR}/.env"
  echo "       nano ${REPO_DIR}/.env"
  echo ""
  echo "  Then re-run: systemctl start ${SERVICE_NAME}"
fi

# ── 5. Run migrations ───────────────────────────────────────────────────────
if [ -f "${REPO_DIR}/.env" ]; then
  echo "→ Running database migrations..."
  cd "${REPO_DIR}/backend"
  export PYTHONPATH="${REPO_DIR}/shared/contracts/src:${REPO_DIR}/platform/ai/src:${REPO_DIR}/backend/src:${REPO_DIR}/apps/whatsapp-assistant/src"
  "${VENV_DIR}/bin/alembic" upgrade head
fi

# ── 6. Frontend directory ───────────────────────────────────────────────────
echo "→ Creating frontend directory ${FRONTEND_DIR}..."
mkdir -p "${FRONTEND_DIR}"
chown -R www-data:www-data "${FRONTEND_DIR}"

# ── 7. systemd service ──────────────────────────────────────────────────────
echo "→ Installing systemd service..."
cp "${REPO_DIR}/infra/mesiri.service" "/etc/systemd/system/${SERVICE_NAME}.service"
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"

if [ -f "${REPO_DIR}/.env" ]; then
  systemctl restart "${SERVICE_NAME}"
  echo "→ Waiting for service to start..."
  sleep 4
  if curl -sf http://127.0.0.1:8000/health > /dev/null; then
    echo "  ✓ Service is healthy"
  else
    echo "  ✗ Service did not respond — check: journalctl -u ${SERVICE_NAME} -n 50"
  fi
else
  echo "  Service not started yet (waiting for .env)."
fi

# ── 8. GitHub Actions deploy key ────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════"
echo "  NEXT STEPS — do these manually"
echo "════════════════════════════════════════════"
echo ""
echo "1. Generate a deploy SSH key pair (if you haven't already):"
echo ""
echo "     ssh-keygen -t ed25519 -C 'github-actions-deploy' -f ~/.ssh/github_deploy"
echo ""
echo "2. Add the PUBLIC key to the VPS authorized_keys:"
echo ""
echo "     cat ~/.ssh/github_deploy.pub >> ~/.ssh/authorized_keys"
echo ""
echo "3. Add the PRIVATE key to GitHub Secrets:"
echo "   Repo → Settings → Secrets and variables → Actions → New repository secret"
echo ""
echo "   Secret name        Value"
echo "   ─────────────────  ─────────────────────────────────────"
echo "   VPS_SSH_KEY        (paste contents of ~/.ssh/github_deploy)"
echo "   VPS_HOST           187.127.180.98"
echo "   VPS_USER           root"
echo ""
echo "4. Fill in /opt/mesiri/.env with production values (see .env.example)"
echo ""
echo "5. Push any commit to main and watch Actions deploy automatically."
echo ""
echo "Useful commands:"
echo "  journalctl -u mesiri -f          # live logs"
echo "  systemctl status mesiri           # service status"
echo "  systemctl restart mesiri          # manual restart"
echo ""
