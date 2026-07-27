"""Pure DPR (#16 Daily Report Generation) assembly logic -- no I/O.

infrastructure/postgres/repositories/dpr.py fetches the raw rows; this
package shapes them into the payload JSONB / render-ready structures, kept
separate so the shaping logic is unit-testable without a live database.
"""
