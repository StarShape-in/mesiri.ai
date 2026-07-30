"""Materials integrity: block double reversals and case-variant catalogue names.

Materials records are append-only by design (migration `0270`): a mistake is
corrected by posting an opposite-direction row, never by editing or deleting.
That makes every corruption permanent until a human notices it, which is why
these two guards belong in the database rather than only in application code.

**Double reversal.** `domains/materials/router.py`'s reverse endpoints write a
new row carrying `reverses_movement_id`, but nothing has ever checked whether
that original was already reversed. `0310`'s
`UNIQUE(source_type, source_id, movement_type)` does not catch it: each reversal
mints a fresh `source_id`, so the pair is always unique. Reversing a 50-bag
receipt twice therefore leaves stock 100 bags light, permanently. The partial
unique indexes here make one-original-at-most-one-reversal a database fact,
enforced even against direct SQL or a future third write path.

**Case-variant catalogue names.** `0180`'s
`uq_materials_catalog_org_name(organization_id, name)` is exact-match, so
"Cement", "cement" and "Cement " are three materials and one stockpile becomes
three. Worse, the WhatsApp resolver (`find_by_name_exact_active`) *is*
`lower()`-based and takes `.first()`, so with duplicates present it resolves to
an arbitrary one -- the same message can hit either row. Existing duplicates are
merged here before the case-insensitive index is created.

The merge is the only step in this migration that changes data, and it is
deliberately conservative:

- The survivor is the row with movement history, or the oldest row when no
  candidate has any. Ledger history is repointed, never deleted.
- If two colliding rows **both** have movements and disagree on Stock Unit, this
  migration RAISES rather than guesses. There is no unit conversion in V1, so
  merging "Cement (bags)" into "Cement (kg)" would silently invent a quantity.
  That needs a human decision, not a default.
- Pre-existing double reversals likewise abort with the offending ids listed.
  Deleting rows from an append-only ledger to make an index build is never an
  acceptable trade.

Indexes are created normally rather than CONCURRENTLY: this migration also
merges data, and keeping the whole thing in one transaction (so a late failure
rolls back the merge) is worth more than avoiding a brief write lock at V1 table
sizes. Anyone running this against a very large production table should split
the index steps out and use CONCURRENTLY there instead.

The two composite indexes at the end match what the inflow/outflow list queries
actually do -- filter on `(organization_id, project_id)` plus an `occurred_date`
range, ordered by `occurred_date DESC` -- which nothing has indexed until now.

Revision ID: 0459
Revises: 0458
Create Date: 2026-07-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0459"
down_revision = "0458"
branch_labels = None
depends_on = None


_MOVEMENT_TABLES = ("material_receipts", "material_usage")


def _abort_on_existing_double_reversals(conn) -> None:
    """Refuse to build the uniqueness guard over data that already violates it."""
    offenders: list[str] = []
    for table in _MOVEMENT_TABLES:
        rows = conn.execute(
            sa.text(
                f"""
                SELECT reverses_movement_id, COUNT(*) AS n
                FROM {table}
                WHERE reverses_movement_id IS NOT NULL
                GROUP BY reverses_movement_id
                HAVING COUNT(*) > 1
                """  # noqa: S608 - table name is from a module-level constant
            )
        ).fetchall()
        offenders.extend(f"{table}: original {r[0]} reversed {r[1]} times" for r in rows)

    if offenders:
        raise RuntimeError(
            "Cannot enforce one-reversal-per-movement: this database already "
            "contains double reversals, so stock for the affected materials is "
            "already wrong. These need a human decision (which correction was "
            "intended) before the guard can be added -- resolving them by "
            "deleting ledger rows is not acceptable.\n  " + "\n  ".join(offenders)
        )


def _merge_case_variant_materials(conn) -> None:
    """Collapse per-org name collisions that differ only by case/whitespace."""
    groups = conn.execute(
        sa.text(
            """
            SELECT organization_id, lower(btrim(name)) AS norm_name,
                   array_agg(id ORDER BY created_at) AS ids
            FROM materials_catalog
            GROUP BY organization_id, lower(btrim(name))
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()

    for org_id, norm_name, ids in groups:
        # How much real history does each candidate carry, and in which unit?
        stats = conn.execute(
            sa.text(
                """
                SELECT c.id,
                       c.default_unit_id,
                       (SELECT COUNT(*) FROM material_movements m
                         WHERE m.material_id = c.id) AS movement_count
                FROM materials_catalog c
                WHERE c.id = ANY(:ids)
                ORDER BY c.created_at
                """
            ),
            {"ids": list(ids)},
        ).fetchall()

        with_history = [s for s in stats if s[2] > 0]
        distinct_units = {s[1] for s in with_history}
        if len(with_history) > 1 and len(distinct_units) > 1:
            raise RuntimeError(
                "Cannot merge duplicate materials named "
                f"{norm_name!r} in organization {org_id}: two or more of them "
                "already have recorded movements in DIFFERENT stock units "
                f"(catalog ids {[str(s[0]) for s in with_history]}). V1 has no "
                "unit conversion, so merging them would invent quantities. "
                "Decide which unit is correct and reconcile these by hand first."
            )

        # Prefer the row that carries history; otherwise the oldest.
        survivor = with_history[0][0] if with_history else stats[0][0]
        losers = [s[0] for s in stats if s[0] != survivor]
        if not losers:
            continue

        for table in (*_MOVEMENT_TABLES, "material_movements"):
            conn.execute(
                sa.text(
                    f"UPDATE {table} SET material_id = :survivor "  # noqa: S608
                    "WHERE material_id = ANY(:losers)"
                ),
                {"survivor": survivor, "losers": losers},
            )
        conn.execute(
            sa.text("DELETE FROM materials_catalog WHERE id = ANY(:losers)"),
            {"losers": losers},
        )


def upgrade() -> None:
    conn = op.get_bind()

    _abort_on_existing_double_reversals(conn)
    _merge_case_variant_materials(conn)

    # One original may be corrected at most once. Partial, because the vast
    # majority of rows are ordinary movements with a NULL here.
    for table in _MOVEMENT_TABLES:
        op.create_index(
            f"uq_{table}_reverses_movement_id",
            table,
            ["reverses_movement_id"],
            unique=True,
            postgresql_where=sa.text("reverses_movement_id IS NOT NULL"),
        )

    # Case/whitespace-insensitive uniqueness. The exact-match constraint from
    # 0180 stays: it is strictly weaker, so it can never reject anything this
    # one accepts, and dropping it would be churn for no gain.
    op.create_index(
        "uq_materials_catalog_org_name_ci",
        "materials_catalog",
        ["organization_id", sa.text("lower(btrim(name))")],
        unique=True,
    )

    # Matches the inflow/outflow list access pattern (filter + ORDER BY).
    for table in _MOVEMENT_TABLES:
        op.create_index(
            f"ix_{table}_org_project_date",
            table,
            ["organization_id", "project_id", sa.text("occurred_date DESC")],
        )


def downgrade() -> None:
    for table in _MOVEMENT_TABLES:
        op.drop_index(f"ix_{table}_org_project_date", table_name=table)
    op.drop_index("uq_materials_catalog_org_name_ci", table_name="materials_catalog")
    for table in _MOVEMENT_TABLES:
        op.drop_index(f"uq_{table}_reverses_movement_id", table_name=table)
    # The merge is deliberately not reversed: the duplicate catalog rows are
    # gone and their history now points at the survivor. Recovery is
    # restore-from-backup, which is why this migration is run alone.
