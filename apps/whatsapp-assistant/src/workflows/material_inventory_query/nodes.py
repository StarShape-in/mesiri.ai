"""Nodes for the material inventory-query workflow."""

from __future__ import annotations

from typing import Any

from ..state import WorkflowGraphState


def _fmt(value: Any) -> str:
    """Render a stock quantity without a noisy trailing .0 for whole numbers."""
    number = float(value)
    if number == int(number):
        return str(int(number))
    return f"{number:.2f}".rstrip("0").rstrip(".")


def generate_inventory_reply(state: WorkflowGraphState) -> dict:
    """Read the injected stock levels and format the reply. No draft_action --
    this is read-only, so WorkflowRuntime completes it without a confirmation."""
    fields = state.get("collected_fields", {})
    levels: list[dict] = fields.get("inventory_levels") or []
    material_name = fields.get("material_name")

    if not levels:
        if material_name:
            return {
                "pending_prompt": f"I don't have any recorded stock for {material_name} yet."
            }
        return {"pending_prompt": "I don't have any recorded material stock yet."}

    if material_name and len(levels) == 1:
        level = levels[0]
        lines = [
            f"{level['material_name']}: {_fmt(level['current_stock'])} {level['unit']} in stock",
            f"({_fmt(level['received'])} received, {_fmt(level['used'])} used)",
        ]
        return {"pending_prompt": "\n".join(lines)}

    lines = ["*Current inventory*", ""]
    for level in levels:
        lines.append(
            f"   • {level['material_name']}: {_fmt(level['current_stock'])} {level['unit']}"
        )
    return {"pending_prompt": "\n".join(lines)}
