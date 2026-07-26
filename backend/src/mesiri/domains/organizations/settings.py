"""Organization settings — the catalog of per-tenant tunable rules.

Pure definitions, no I/O: what settings exist, what shape each holds, and
what an org that has never configured one falls back to. The store
(infrastructure/postgres/repositories/organization_settings.py) reads and
writes rows; this module is the single place that decides what a valid
setting *is*, so an unknown key can be rejected at the API boundary rather
than silently persisted and never read by anything.

Defaults matter more than usual here: no row exists for any org until
someone changes something in the control panel, so the default IS the
behaviour for every existing tenant. Each default below is chosen to match
what the code did before the setting existed.
"""

from __future__ import annotations

from dataclasses import dataclass

# Every role the system recognises (users/router.py's _VALID_ROLES). Kept as
# a frozenset here so a settings payload naming a role that doesn't exist is
# rejected at the boundary instead of silently never matching anyone.
VALID_ROLES: frozenset[str] = frozenset(
    {"ADMIN", "PROJECT_MANAGER", "SITE_ENGINEER", "FINANCE"}
)

# Which roles may create a materials_catalog entry directly from a WhatsApp
# report (STA-139). Default is Admin + Project Manager: before this setting
# existed the WhatsApp path could not create catalog entries at all, so the
# conservative default keeps casual field reports from populating a shared
# catalog with typos, while still unblocking the people who own it.
WHATSAPP_MATERIAL_CREATE_ROLES = "whatsapp_material_create_roles"
FINANCE_SETTINGS = "finance_settings"

DEFAULT_FINANCE_SETTINGS = {
    "base_currency": "INR",
    "currency_symbol": "₹",
    "fiscal_year_start": "04-01",
    "low_float_threshold": 50000.0,
    "auto_approval_limit": 5000.0,
    "require_receipt_above": 1000.0,
    "duplicate_window_hours": 24,
    "default_tax_rate": 18.0,
    "enabled_payment_methods": ["bank_transfer", "cash", "upi", "cheque", "card"],
    "low_balance_warning_enabled": True,
    "transfer_receipt_enabled": True,
    "expense_card_enabled": True,
    "weekly_digest_enabled": True,
    "weekly_digest_schedule": "weekly_monday",
}


@dataclass(frozen=True, slots=True)
class SettingSpec:
    """What a setting holds and what it means when it's never been set."""

    key: str
    default: object
    description: str


_SPECS: dict[str, SettingSpec] = {
    WHATSAPP_MATERIAL_CREATE_ROLES: SettingSpec(
        key=WHATSAPP_MATERIAL_CREATE_ROLES,
        default=["ADMIN", "PROJECT_MANAGER"],
        description=(
            "Roles allowed to add a new material to the catalog directly from a "
            "WhatsApp report. Anyone else is told to ask their admin."
        ),
    ),
    FINANCE_SETTINGS: SettingSpec(
        key=FINANCE_SETTINGS,
        default=DEFAULT_FINANCE_SETTINGS,
        description="Organization-wide financial preferences & WhatsApp assistant policies.",
    ),
}


def is_known_key(key: str) -> bool:
    return key in _SPECS


def default_for(key: str) -> object:
    """The value an org that has never configured `key` behaves as."""
    spec = _SPECS.get(key)
    if spec is None:
        raise KeyError(f"unknown organization setting: {key}")
    return spec.default


def all_specs() -> tuple[SettingSpec, ...]:
    """Every known setting — what the control panel renders its form from."""
    return tuple(_SPECS.values())


def validate_role_list(value: object) -> list[str]:
    """Coerce and validate a roles payload, raising ValueError on anything
    that isn't a list of known role names.

    Uppercases on the way in so the stored value is always canonical and the
    read path never has to case-normalize before comparing.
    """
    if not isinstance(value, list):
        raise ValueError("value must be a list of role names")
    roles: list[str] = []
    for entry in value:
        if not isinstance(entry, str):
            raise ValueError("value must be a list of role names")
        role = entry.strip().upper()
        if role not in VALID_ROLES:
            raise ValueError(f"unknown role: {entry}")
        if role not in roles:
            roles.append(role)
    return roles


def validate(key: str, value: object) -> object:
    """Validate `value` for `key`, returning the canonical form to persist."""
    if not is_known_key(key):
        raise ValueError(f"unknown organization setting: {key}")
    if key == WHATSAPP_MATERIAL_CREATE_ROLES:
        return validate_role_list(value)
    return value


def role_allowed(role: str | None, allowed: object) -> bool:
    """True if `role` appears in an `allowed` roles setting value.

    Defensive about the stored shape: a hand-edited or legacy row that isn't
    a list of strings denies rather than crashes the WhatsApp reply, since
    this runs inside the inbound journey where an exception costs the user
    their whole message.
    """
    if not role or not isinstance(allowed, list):
        return False
    return role.strip().upper() in {
        str(entry).strip().upper() for entry in allowed if isinstance(entry, str)
    }
