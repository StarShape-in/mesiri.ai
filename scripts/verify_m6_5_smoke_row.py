"""Verify M6.5 smoke test workflow_instances row on prod."""
import json
import os
import sys

import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(
    os.environ["MESIRI_VPS_HOST"],
    username=os.environ["MESIRI_VPS_USER"],
    password=os.environ["MESIRI_VPS_PASSWORD"],
)

sql = (
    "SELECT id::text, organization_id::text, user_id::text, workflow_key, phase, "
    "correlation_id, status, state::text FROM workflow_instances ORDER BY id DESC LIMIT 1;"
)
cmd = f'docker exec mesiri-postgres psql -U mesiri -d mesiri -t -A -c "{sql}"'
_, o, _ = c.exec_command(cmd)
row = o.read().decode().strip()

parts = row.split("|")
if len(parts) < 8:
    print("FAIL: unexpected row shape", len(parts), file=sys.stderr)
    sys.exit(1)

wi_id, org, user, wk, phase, corr, status, state_json = parts[:8]
state = json.loads(state_json)
draft = state.get("draft_action") or {}
prompt = state.get("pending_prompt") or ""

expected_org = "562aa8d5-5376-4c8b-8b11-9cfeb6ceea33"
expected_user = "4d1f0571-6eba-4eb1-8968-f0fc837ac324"

checks = {
    "org_uuid": org == expected_org,
    "user_uuid": user == expected_user,
    "state_v2": state.get("version") == "v2",
    "draft_v2": draft.get("version") == "v2",
    "canonical_org_in_state": state.get("organization_id") == expected_org,
    "canonical_user_in_state": state.get("user_id") == expected_user,
    "phase_awaiting": phase == "awaiting_confirmation",
    "workflow_key": wk == "material.receipt",
    "has_prompt": bool(prompt),
    "prompt_has_yes": "YES" in prompt.upper(),
}

for k, v in checks.items():
    print(f"{k}={v}")
print(f"workflow_instance_id={wi_id}")
print(f"correlation_id={corr}")

_, o, _ = c.exec_command(
    "docker exec mesiri-postgres psql -U mesiri -d mesiri -t -A -c "
    "'SELECT COUNT(*) FROM workflow_instances;'"
)
count = o.read().decode().strip()
print(f"workflow_instances_count={count}")

c.close()
sys.exit(0 if all(checks.values()) else 1)
