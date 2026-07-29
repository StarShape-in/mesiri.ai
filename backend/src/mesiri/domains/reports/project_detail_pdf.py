"""On-demand "project/site details" PDF rendering, backend-native (no Playwright).

Modeled on domains/dpr/pdf.py's header + KPI-tiles + table layout, not
domains/reports/pdf_table.py's single flat table -- a project/site summary
is a record card plus several operational rollups, not one list. Pure
function, no I/O -- unit-testable without a live database. fpdf2 is
imported lazily so the core test suite runs without it installed.
"""

from __future__ import annotations

from typing import Any

_PAGE_WIDTH_MM = 210 - 2 * 15  # A4 minus 15mm margins each side


def render_project_detail_pdf_bytes(
    *,
    name: str,
    code: str | None,
    location: str | None,
    status: str | None,
    sites: list[dict[str, Any]] | None,
    member_count: int | None,
    open_issue_count: int,
    open_issues: list[dict[str, Any]],
    headcount: int,
    activity_count: int,
    labour_cost: str,
    expense_total: str | None,
    expense_date_range_label: str | None,
    stock_levels: list[dict[str, Any]],
) -> bytes:
    """Render one project/site's detail summary to PDF bytes.

    `expense_total` is None whenever the seed step withheld the financial
    section (see runtime/inbound_journey.py's `_seed_project_detail_query`
    role gate) -- this renderer never re-derives it from anywhere else, so
    the PDF respects the same visibility rule as the text reply.
    """
    from fpdf import FPDF

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(15, 15, 15)
    pdf.add_page()

    # Header
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 8, name, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(90, 90, 90)
    subtitle = "  |  ".join(
        part for part in [code, location, (status or "").replace("_", " ").title() or None] if part
    )
    if subtitle:
        pdf.cell(0, 6, subtitle, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    # KPI tiles -- spend tile omitted entirely when expense_total is None
    # (withheld by role, see module docstring), not shown as zero.
    tiles = [
        ("Open Issues", str(open_issue_count)),
        ("Workers Today", str(headcount)),
        ("Activities Today", str(activity_count)),
    ]
    if expense_total is not None:
        tiles.append((f"Spend ({expense_date_range_label or 'This Month'})", str(expense_total)))
    tile_w = _PAGE_WIDTH_MM / len(tiles)
    for label, value in tiles:
        x = pdf.get_x()
        y = pdf.get_y()
        pdf.rect(x, y, tile_w - 4, 16)
        pdf.set_xy(x, y + 3)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(tile_w - 4, 6, value, align="C")
        pdf.set_xy(x, y + 10)
        pdf.set_font("Helvetica", "", 8)
        pdf.cell(tile_w - 4, 5, label, align="C")
        pdf.set_xy(x + tile_w, y)
    pdf.ln(20)

    # Sites + team (project-level only -- both None for a site-level query)
    if sites is not None:
        pdf.set_font("Helvetica", "B", 11)
        team_line = f"  |  Team: {member_count} member(s)" if member_count is not None else ""
        pdf.cell(0, 7, f"Sites ({len(sites)}){team_line}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        for site in sites:
            pdf.cell(0, 5, f"- {site.get('name')}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    # Open issues table
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Open Issues", new_x="LMARGIN", new_y="NEXT")
    issue_col_widths = [32, 20, 88, 40]
    issue_headers = ["Type", "Severity", "Narrative", "Reported"]
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(230, 230, 230)
    for header, width in zip(issue_headers, issue_col_widths, strict=False):
        pdf.cell(width, 7, header, border=1, fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 8)
    if not open_issues:
        pdf.cell(sum(issue_col_widths), 7, "No open issues.", border=1)
        pdf.ln()
    for issue in open_issues:
        row = [
            str(issue.get("issue_type") or "-"),
            str(issue.get("severity") or "-"),
            str(issue.get("narrative") or "-")[:60],
            str(issue.get("occurred_at") or "-"),
        ]
        for value, width in zip(row, issue_col_widths, strict=False):
            pdf.cell(width, 7, value, border=1)
        pdf.ln()

    pdf.ln(4)

    # Stock table
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Material Stock", new_x="LMARGIN", new_y="NEXT")
    stock_col_widths = [70, 35, 35, 40]
    stock_headers = ["Material", "Current Stock", "Unit", "Used (Total)"]
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(230, 230, 230)
    for header, width in zip(stock_headers, stock_col_widths, strict=False):
        pdf.cell(width, 7, header, border=1, fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 8)
    if not stock_levels:
        pdf.cell(sum(stock_col_widths), 7, "No recorded material stock.", border=1)
        pdf.ln()
    for level in stock_levels:
        row = [
            str(level.get("material_name") or "-"),
            str(level.get("current_stock", "-")),
            str(level.get("unit") or "-"),
            str(level.get("used", "-")),
        ]
        for value, width in zip(row, stock_col_widths, strict=False):
            pdf.cell(width, 7, value, border=1)
        pdf.ln()

    # Footer -- auto_page_break must be off here, same reasoning as
    # domains/dpr/pdf.py's identical comment.
    pdf.set_auto_page_break(auto=False)
    pdf.set_y(-20)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 10, "Generated on-demand by Mesiri", align="C")

    return bytes(pdf.output())
