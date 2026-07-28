"""domains/reports/pdf_table.py -- pure fpdf2 rendering, no I/O.

Generalizes domains/dpr/pdf.py's approach (see test_dpr_pdf.py) into a plain
columns+rows table, used by the WhatsApp assistant's finance-query "send as
PDF" workflow (runtime/inbound_journey.py) as well as any future dashboard
export that just needs a flat table.
"""

from __future__ import annotations

from mesiri.domains.reports.pdf_table import render_table_pdf


def test_renders_valid_pdf_bytes_for_populated_rows():
    pdf_bytes = render_table_pdf(
        title="Account Balances",
        subtitle=None,
        columns=["Account", "Balance"],
        rows=[["Site Cash", "12500.00"], ["Company Account", "450000.00"]],
        column_widths=[100, 80],
    )
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500


def test_renders_without_error_for_empty_rows():
    """No matching records yet (e.g. a brand new org) must still produce a
    valid PDF showing the empty_message, not raise on an empty rows list."""
    pdf_bytes = render_table_pdf(
        title="Expenses",
        subtitle="Today | 0 expenses | Total: 0",
        columns=["Date", "Amount", "Description"],
        rows=[],
        empty_message="No matching expenses found.",
    )
    assert pdf_bytes.startswith(b"%PDF")


def test_handles_none_values_in_row_cells():
    """A row with a missing optional value (e.g. no description) must render
    as '-' rather than crash str()-ing None."""
    pdf_bytes = render_table_pdf(
        title="Expenses",
        subtitle=None,
        columns=["Date", "Amount", "Description"],
        rows=[["2026-07-20", "500", None]],
    )
    assert pdf_bytes.startswith(b"%PDF")


def test_column_widths_default_to_even_split_when_omitted():
    """No column_widths given -- must not raise (splits page width evenly)."""
    pdf_bytes = render_table_pdf(
        title="Test",
        subtitle=None,
        columns=["A", "B", "C"],
        rows=[["1", "2", "3"]],
    )
    assert pdf_bytes.startswith(b"%PDF")
