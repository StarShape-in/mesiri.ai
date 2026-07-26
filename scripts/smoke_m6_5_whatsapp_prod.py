"""M6.5 production WhatsApp smoke test — material receipt through full v2 pipeline.

Posts a signed webhook to localhost, then verifies workflow_instances and logs.
Does NOT confirm the workflow (M7 resume not implemented).

Usage:
    python scripts/smoke_m6_5_whatsapp_prod.py
"""

from __future__ import annotations

import os
import sys
import time

import paramiko

HOST = os.environ["MESIRI_VPS_HOST"]
USER = os.environ["MESIRI_VPS_USER"]
PASS = os.environ["MESIRI_VPS_PASSWORD"]
ROOT = "/opt/mesiri"
MESSAGE = "50 bags of UltraTech cement arrived at site today from ABC Suppliers."

# Remote runner script (executed on VPS with prod .env + PYTHONPATH).
REMOTE_RUNNER = r'''
import hashlib
import hmac
import json
import os
import re
import sys
import time
import uuid
from datetime import UTC, datetime

MESSAGE = """__MESSAGE__"""

def load_env(path):
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

load_env("/opt/mesiri/.env")
app_secret = os.environ.get("WHATSAPP_APP_SECRET", "")
if not app_secret:
    print("FAIL: WHATSAPP_APP_SECRET missing")
    sys.exit(1)

def psql(sql):
    import subprocess
    r = subprocess.run(
        ["docker", "exec", "mesiri-postgres", "psql", "-U", "mesiri", "-d", "mesiri", "-t", "-A", "-c", sql],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print("SQL error:", r.stderr or r.stdout)
        raise SystemExit(2)
    return r.stdout.strip()

def digits(s):
    return re.sub(r"\D", "", s or "")

# --- Pick sender from external_identities ---------------------------------
rows = psql(
    "SELECT ei.external_subject, ei.user_id, cu.canonical_user_id::text, "
    "co.canonical_organization_id::text "
    "FROM external_identities ei "
    "JOIN context_users cu ON cu.id = ei.user_id "
    "JOIN organization_memberships om ON om.user_id = cu.id AND om.is_active = true "
    "JOIN context_organizations co ON co.id = om.organization_id "
    "WHERE ei.provider = 'whatsapp' "
    "ORDER BY ei.external_subject LIMIT 5"
)
if not rows:
    print("FAIL: no whatsapp external_identities with active membership")
    sys.exit(1)

picked = None
for line in rows.splitlines():
    parts = line.split("|")
    if len(parts) < 4:
        continue
    ext_subject, ctx_user, canon_user, canon_org = parts[:4]
  # Prefer digit-only wa_id for Meta realism; also store formatted subject.
    wa_from = digits(ext_subject) or ext_subject
    picked = {
        "external_subject": ext_subject,
        "wa_from": wa_from,
        "ctx_user": ctx_user,
        "canon_user": canon_user,
        "canon_org": canon_org,
    }
    break

print("PICKED_SENDER", json.dumps(picked))

# Ensure external_identities also has digit-only subject for resolver lookup.
alt = picked["wa_from"]
if alt and alt != picked["external_subject"]:
    psql(
        "INSERT INTO external_identities (id, provider, external_subject, user_id) "
        f"VALUES ('ext_whatsapp_{alt}', 'whatsapp', '{alt}', '{picked['ctx_user']}') "
        "ON CONFLICT (provider, external_subject) DO UPDATE SET user_id = EXCLUDED.user_id"
    )
    print("ENSURED_DIGIT_SUBJECT", alt)

before_count = int(psql("SELECT COUNT(*) FROM workflow_instances") or "0")
msg_id = f"wamid.m65.{uuid.uuid4().hex[:12]}"
cor_id = f"cor_m65_{uuid.uuid4().hex[:8]}"
ts = str(int(datetime.now(UTC).timestamp()))

payload = {
    "object": "whatsapp_business_account",
    "entry": [{
        "id": "WABA_ID",
        "changes": [{
            "field": "messages",
            "value": {
                "messaging_product": "whatsapp",
                "metadata": {
                    "display_phone_number": "15550001111",
                    "phone_number_id": os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "PHONE_ID"),
                },
                "contacts": [{
                    "wa_id": picked["wa_from"],
                    "profile": {"name": "M6.5 Smoke"},
                }],
                "messages": [{
                    "from": picked["wa_from"],
                    "id": msg_id,
                    "timestamp": ts,
                    "type": "text",
                    "text": {"body": MESSAGE},
                }],
            },
        }],
    }],
}

body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
sig = "sha256=" + hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()

import urllib.request
req = urllib.request.Request(
    "http://127.0.0.1:8000/webhook",
    data=body,
    headers={
        "Content-Type": "application/json",
        "X-Hub-Signature-256": sig,
    },
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        print("WEBHOOK_STATUS", resp.status)
except Exception as exc:
    print("WEBHOOK_ERROR", exc)
    sys.exit(3)

# Wait for async pipeline
for i in range(30):
    time.sleep(2)
    after = int(psql("SELECT COUNT(*) FROM workflow_instances") or "0")
    if after > before_count:
        print("WORKFLOW_ROW_APPEARED", after - before_count)
        break
else:
    print("FAIL: no new workflow_instances row within 60s")
    sys.exit(4)

row = psql(
    "SELECT id::text, organization_id::text, user_id::text, workflow_key, phase, "
    "correlation_id, status, state::text "
    "FROM workflow_instances ORDER BY created_at DESC NULLS LAST, id DESC LIMIT 1"
)
print("WORKFLOW_ROW", row)

# Parse JSON state for v2 assertions
parts = row.split("|")
if len(parts) >= 8:
    state_json = parts[7]
    try:
        state = json.loads(state_json)
        print("STATE_VERSION", state.get("version"))
        print("STATE_ORG", state.get("organization_id"))
        print("STATE_USER", state.get("user_id"))
        print("STATE_PHASE", state.get("phase"))
        da = state.get("draft_action") or {}
        print("DRAFT_VERSION", da.get("version"))
        print("DRAFT_ORG", da.get("organization_id"))
        print("PENDING_PROMPT", (state.get("pending_prompt") or "")[:120])
    except json.JSONDecodeError as exc:
        print("STATE_JSON_ERROR", exc)

# Recent logs
import subprocess
log = subprocess.run(
    ["tail", "-80", "/tmp/mesiri_uvicorn.log"],
    capture_output=True,
    text=True,
)
for line in log.stdout.splitlines():
    if any(k in line for k in (
        "ResolvedContext", "CanonicalEvent", "PlannerDecision", "WorkflowRun",
        "context.", "workflow.", msg_id, cor_id,
    )):
        print("LOG", line)

print("EXPECTED_CANON_ORG", picked["canon_org"])
print("EXPECTED_CANON_USER", picked["canon_user"])
print("MSG_ID", msg_id)
'''


def main() -> int:
    message_escaped = MESSAGE.replace("\\", "\\\\").replace('"', '\\"')
    runner = REMOTE_RUNNER.replace("__MESSAGE__", message_escaped)
    remote_path = f"{ROOT}/scripts/_m65_smoke_runner.py"

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)

    # Ensure assistant is running
    client.exec_command(
        f"cd {ROOT} && /opt/mesiri/.venv/bin/python scripts/restart_whatsapp_assistant.py"
    )
    time.sleep(6)

    hex_content = runner.encode("utf-8").hex()
    write_cmd = (
        f"python3 -c \"import binascii; open('{remote_path}', 'wb')"
        f".write(binascii.unhexlify('{hex_content}'))\""
    )
    client.exec_command(f"mkdir -p {ROOT}/scripts")
    _, stdout, stderr = client.exec_command(write_cmd)
    stderr.read()

    cmd = (
        f"cd {ROOT} && "
        "export PYTHONPATH=/opt/mesiri/shared/contracts/src:/opt/mesiri/platform/ai/src:"
        "/opt/mesiri/backend/src:/opt/mesiri/apps/whatsapp-assistant/src && "
        "/opt/mesiri/.venv/bin/python scripts/_m65_smoke_runner.py"
    )
    _, stdout, stderr = client.exec_command(cmd, get_pty=True)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    print(out)
    if err.strip():
        print(err, file=sys.stderr)

    client.exec_command(f"rm -f {remote_path}")
    client.close()

    failed = "FAIL:" in out or "WEBHOOK_ERROR" in out or "STATE_VERSION" not in out
    if "STATE_VERSION" in out:
        for line in out.splitlines():
            if line.startswith("STATE_VERSION"):
                _, _, ver = line.partition(" ")
                if ver.strip() != "v2":
                    failed = True
    if "WORKFLOW_ROW_APPEARED" not in out:
        failed = True

    if failed:
        print("\nSMOKE RESULT: FAIL")
        return 1

    print("\nSMOKE RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
