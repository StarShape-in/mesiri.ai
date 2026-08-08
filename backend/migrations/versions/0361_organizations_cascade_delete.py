"""Make tenant deletion a database-enforced cascade from organizations.

Deleting a tenant used to be a ~90-line hand-ordered sequence of DELETEs in
admin/router.delete_organization (apps/whatsapp-assistant), because almost
none of the tenant-scoped tables had ON DELETE CASCADE on their path back to
organizations.id. Every schema change that added an org-scoped table was a
silent landmine: the finance refactor (0320-0340) added expense_categories,
expense_attachments, expense_payments, budgets, budget_allocations and
renamed finance_accounts/finance_account_transactions, and the handler was
never updated — tenant deletion started 500ing (missing relation) and would
have hit FK violations on the new child tables even once that was fixed.

This migration moves that guarantee into the schema so it can't drift again:
deleting a row from `organizations` now cascades to every tenant-scoped row
by itself. `users.organization_id` and `projects.organization_id` had *no*
FK to organizations at all (index only) — added here. Every other table
already had the FK; this only adds `ON DELETE CASCADE` to it.

Scope of what's actually changed, and why nothing else needs to move: a
single DELETE statement (including everything it cascades into) is checked
for FK violations once, at the end of that statement — not row-by-row as
rows disappear. So the only FKs that need an explicit CASCADE are the ones
that are the *sole reachable path* from organizations.id down to a given
row. Every other reference between two rows that both get swept up by one
of those direct paths (created_by/updated_by -> users, expenses.project_id
-> projects, the material_receipts<->material_usage reversal cross-cycle
added in 0270, expense_categories.parent_category_id self-reference, etc.)
is satisfied automatically because both sides vanish in the same statement,
exactly like the manual UPDATE ... SET reverses_movement_id = NULL step the
old handler used to do by hand for that one cycle. Left untouched, and out
of scope: the context_organizations-rooted subsystem (context_projects,
context_sites, context_users, organization_memberships, roles, project/site
_memberships, external_identities, user_context_preferences) — a distinct
tenant root the delete handler never touched, and units_of_measure /
unit_aliases, which are global catalogs, not tenant-scoped.

Revision ID: 0361
Revises: 0350
Create Date: 2026-07-24
"""

from __future__ import annotations

from alembic import op

revision = "0361"
down_revision = "0350"
branch_labels = None
depends_on = None

# (table, constraint_name, local_column, referred_table, referred_column)
# for FKs that already exist and just need ON DELETE CASCADE added.
_EXISTING_FKS_TO_CASCADE = [
    ("money_accounts", "finance_accounts_organization_id_fkey", "organization_id", "organizations", "id"),
    ("expense_categories", "expense_categories_organization_id_fkey", "organization_id", "organizations", "id"),
    ("expenses", "expenses_organization_id_fkey", "organization_id", "organizations", "id"),
    ("expense_payments", "expense_payments_organization_id_fkey", "organization_id", "organizations", "id"),
    ("money_transactions", "fk_money_transactions_organization_id", "organization_id", "organizations", "id"),
    ("budgets", "budgets_organization_id_fkey", "organization_id", "organizations", "id"),
    ("material_receipts", "material_receipts_organization_id_fkey", "organization_id", "organizations", "id"),
    ("material_usage", "material_usage_organization_id_fkey", "organization_id", "organizations", "id"),
    ("material_movements", "material_movements_organization_id_fkey", "organization_id", "organizations", "id"),
    ("equipment_events", "equipment_events_organization_id_fkey", "organization_id", "organizations", "id"),
    ("labour_attendance", "labour_attendance_organization_id_fkey", "organization_id", "organizations", "id"),
    ("materials_catalog", "materials_catalog_organization_id_fkey", "organization_id", "organizations", "id"),
    ("timeline_entries", "timeline_entries_organization_id_fkey", "organization_id", "organizations", "id"),
    ("workflow_instances", "workflow_instances_organization_id_fkey", "organization_id", "organizations", "id"),
    ("inbound_messages", "fk_inbound_messages_organization_id", "organization_id", "organizations", "id"),
    # Child tables with no organization_id of their own — CASCADE here is
    # their only reachable path down from organizations.
    ("expense_attachments", "expense_attachments_expense_id_fkey", "expense_id", "expenses", "id"),
    ("budget_allocations", "budget_allocations_budget_id_fkey", "budget_id", "budgets", "id"),
    (
        "labour_attendance_entries",
        "labour_attendance_entries_attendance_id_fkey",
        "attendance_id",
        "labour_attendance",
        "id",
    ),
    ("interactions", "interactions_user_id_fkey", "user_id", "users", "id"),
]

# users.organization_id and projects.organization_id never had an FK to
# organizations at all (create_table only added an index) — add them fresh.
_NEW_FKS = [
    ("users", "fk_users_organization_id", "organization_id", "organizations", "id"),
    ("projects", "fk_projects_organization_id", "organization_id", "organizations", "id"),
]


def upgrade() -> None:
    for table, constraint, local_col, ref_table, ref_col in _EXISTING_FKS_TO_CASCADE:
        op.drop_constraint(constraint, table, type_="foreignkey")
        op.create_foreign_key(
            constraint, table, ref_table, [local_col], [ref_col], ondelete="CASCADE"
        )

    for table, constraint, local_col, ref_table, ref_col in _NEW_FKS:
        op.create_foreign_key(
            constraint, table, ref_table, [local_col], [ref_col], ondelete="CASCADE"
        )


def downgrade() -> None:
    for table, constraint, _local_col, _ref_table, _ref_col in _NEW_FKS:
        op.drop_constraint(constraint, table, type_="foreignkey")

    for table, constraint, local_col, ref_table, ref_col in _EXISTING_FKS_TO_CASCADE:
        op.drop_constraint(constraint, table, type_="foreignkey")
        op.create_foreign_key(constraint, table, ref_table, [local_col], [ref_col])
