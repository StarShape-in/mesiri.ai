"""Unit tests for the Materials -> Finance handoff (Phase C).

The contract being pinned down: a confirmed supplier invoice creates exactly
one unpaid expense, for the amount printed on the document, referencing the
same stored file -- and Materials never writes into Finance's tables to do it.
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from mesiri.domains.materials.invoices import (
    MATERIALS_EXPENSE_CATEGORY,
    build_expense_command,
)


def _command(**overrides):
    defaults = dict(
        invoice_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        site_id=uuid.uuid4(),
        vendor_id=None,
        supplier_name="ABC Traders",
        amount=Decimal("118484"),
        currency="INR",
        occurred_date=datetime.date(2026, 1, 27),
        media_object_key="media/msg-1/img-1",
        created_by=uuid.uuid4(),
        correlation_id="corr-1",
    )
    defaults.update(overrides)
    return build_expense_command(**defaults)


def test_the_expense_is_left_unpaid():
    """Accepting an invoice creates a liability; paying it is a separate
    decision made later by someone else. No account means unpaid in Finance."""
    cmd = _command()

    assert cmd.account_id is None
    assert cmd.paid_from_own_pocket is False


def test_idempotency_key_is_derived_from_the_invoice_not_random():
    """This is what makes 'one confirmation, both modules' safe: a retried
    submission of the same invoice can never produce a second expense."""
    invoice_id = uuid.uuid4()

    first = _command(invoice_id=invoice_id)
    second = _command(invoice_id=invoice_id)

    assert first.idempotency_key == second.idempotency_key
    assert str(invoice_id) in first.idempotency_key


def test_different_invoices_get_different_keys():
    assert _command().idempotency_key != _command().idempotency_key


def test_the_stored_document_is_referenced_not_copied():
    """Finance's attachment points at the same object key the material invoice
    does -- one uploaded file, two referrers."""
    cmd = _command(media_object_key="media/msg-9/img-3")

    assert cmd.media_object_key == "media/msg-9/img-3"


def test_material_spend_is_categorised_explicitly():
    """So material cost is separable in Finance without anyone reclassifying it
    later, rather than falling into the org's default category."""
    cmd = _command()

    assert cmd.category_text == MATERIALS_EXPENSE_CATEGORY
    assert cmd.category_id is None


def test_supplier_survives_as_text_even_when_no_vendor_matched():
    """The document's own words are evidence. Blocking on a tidy vendor list
    would push people back to paper."""
    cmd = _command(vendor_id=None, supplier_name="Bajarangi Traders")

    assert cmd.vendor_id is None
    assert cmd.vendor_text == "Bajarangi Traders"


def test_a_matched_vendor_is_passed_through():
    vendor_id = uuid.uuid4()
    cmd = _command(vendor_id=vendor_id)

    assert cmd.vendor_id == str(vendor_id)


def test_the_expense_is_dated_by_the_invoice_not_by_today():
    """An invoice photographed a week late still belongs to the day it was
    issued, or every spend report drifts."""
    cmd = _command(occurred_date=datetime.date(2026, 1, 27))

    assert cmd.occurred_date == datetime.date(2026, 1, 27)


def test_source_marks_where_the_expense_came_from():
    """So an expense created by the materials flow is distinguishable from one
    somebody typed into Finance directly."""
    assert _command().source == "materials_invoice"


def test_invoice_without_a_document_still_produces_a_valid_command():
    """Not every purchase arrives with a photograph."""
    cmd = _command(media_object_key=None)

    assert cmd.media_object_key is None
    assert cmd.amount == Decimal("118484")
