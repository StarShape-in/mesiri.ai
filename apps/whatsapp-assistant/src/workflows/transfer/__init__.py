"""transfer -- move money between two of the org's own money_accounts.

Two-slot fill (from_account_id, to_account_id), reusing workflows/slots.py
twice -- mirrors expense_capture's single-slot pattern (Finance Module
Slice 1), extended to two independent slots asked in sequence.
"""

from __future__ import annotations
