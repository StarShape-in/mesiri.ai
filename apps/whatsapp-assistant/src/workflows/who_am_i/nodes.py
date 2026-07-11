"""Nodes for the WHO_AM_I identity lookup workflow."""

from __future__ import annotations

from ..state import WorkflowGraphState


def generate_identity_reply(state: WorkflowGraphState) -> dict:
    """Read the injected actor profile and generate the identity summary reply."""
    profile = state.get("collected_fields", {}).get("actor_profile")
    
    if not profile:
        # Fallback if the identity data was somehow missing
        return {"pending_prompt": "I don't have your full profile on hand right now."}
    
    name = profile.get("full_name", "Unknown")
    role = profile.get("role", "").replace("_", " ").title() or "—"
    org = profile.get("org_name", "Unknown")
    
    lines = [
        "*Here is the profile I have for you:*",
        "",
        f"👤 Name: {name}",
        f"🔑 Role: {role}",
        f"🏢 Organization: {org}",
    ]
    
    projects = profile.get("projects", [])
    if projects:
        lines += ["", f"🏗 Projects ({len(projects)}):"]
        for p in projects:
            p_name = p.get("name", "Unknown")
            p_loc = p.get("location")
            p_status = p.get("status", "").replace("_", " ").title()
            
            detail_parts = []
            if p_loc:
                detail_parts.append(f"📍 {p_loc}")
            if p_status:
                detail_parts.append(f"▪️ {p_status}")
                
            detail = " · ".join(detail_parts) if detail_parts else "—"
            lines.append(f"   • {p_name} — {detail}")
    
    sites = profile.get("sites", [])
    if sites:
        lines += ["", f"📍 Sites ({len(sites)}):"]
        for s in sites:
            lines.append(f"   • {s.get('name', 'Unknown')}")
            
    return {"pending_prompt": "\n".join(lines)}
