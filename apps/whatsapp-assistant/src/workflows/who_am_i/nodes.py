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
    query_text = profile.get("query_text", "").casefold()
    
    is_project_query = "project" in query_text
    is_site_query = "site" in query_text
    is_specific_query = is_project_query or is_site_query
    
    lines = []
    
    if not is_specific_query:
        lines.extend([
            "*Here is the profile I have for you:*",
            "",
            f"👤 Name: {name}",
            f"🔑 Role: {role}",
            f"🏢 Organization: {org}",
        ])
    
    if not is_specific_query or is_project_query:
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
        elif is_project_query:
            lines += ["", "🏗 You don't have any projects assigned."]
    
    if not is_specific_query or is_site_query:
        sites = profile.get("sites", [])
        if sites:
            lines += ["", f"📍 Sites ({len(sites)}):"]
            for s in sites:
                lines.append(f"   • {s.get('name', 'Unknown')}")
        elif is_site_query:
            lines += ["", "📍 You don't have any sites assigned."]
            
    # Clean up any leading blank lines from the sub-category replies
    while lines and not lines[0]:
        lines.pop(0)
            
    return {"pending_prompt": "\n".join(lines)}
