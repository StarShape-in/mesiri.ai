"""HTML/CSS layout for the DPR PDF -- a full A4 page, not a WhatsApp card
(contrast channel/receipt/template.py, which renders one screenshot-sized
card). Same lazy-Jinja2-import convention: the core test suite runs without
jinja2 installed unless a document is actually rendered.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .data import DprDocumentData

if TYPE_CHECKING:
    from jinja2 import Template

_INK = "#1D1D1F"
_SUB = "#6E6E73"
_LINE = "#E1E1E6"
_ACCENT = "#0A8F4C"
_WARN = "#B3261E"

_DOCUMENT_TEMPLATE_SRC = """
<!doctype html>
<html><head><meta charset="utf-8"><style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", Inter, system-ui, sans-serif;
    color: {{ ink }}; padding: 28px 34px; font-size: 12px; }
  .header { display: flex; justify-content: space-between; align-items: flex-start;
    border-bottom: 2px solid {{ ink }}; padding-bottom: 12px; }
  .title { font-size: 20px; font-weight: 700; letter-spacing: -0.01em; }
  .subtitle { margin-top: 3px; font-size: 13px; color: {{ sub }}; }
  .code { font-size: 12px; font-weight: 600; color: {{ sub }}; text-align: right; }
  .meta { display: flex; gap: 28px; margin-top: 14px; margin-bottom: 18px; }
  .meta-item .label { font-size: 9.5px; font-weight: 600; letter-spacing: 0.05em;
    text-transform: uppercase; color: {{ sub }}; }
  .meta-item .value { margin-top: 2px; font-size: 15px; font-weight: 600; }
  .section-title { font-size: 13px; font-weight: 700; letter-spacing: 0.02em;
    text-transform: uppercase; color: {{ accent }}; margin-top: 20px; margin-bottom: 8px;
    border-bottom: 1px solid {{ line }}; padding-bottom: 4px; }
  table { width: 100%; border-collapse: collapse; }
  th { text-align: left; font-size: 9.5px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.04em; color: {{ sub }}; padding: 6px 8px; border-bottom: 1px solid {{ line }}; }
  td { padding: 7px 8px; border-bottom: 1px solid {{ line }}; font-size: 11.5px; vertical-align: top; }
  tr:last-child td { border-bottom: none; }
  .empty { color: {{ sub }}; font-style: italic; padding: 10px 8px; }
  .severity-critical, .severity-high { color: {{ warn }}; font-weight: 600; }
  .footer { margin-top: 28px; padding-top: 10px; border-top: 1px solid {{ line }};
    display: flex; justify-content: space-between; font-size: 10px; color: {{ sub }}; }
</style></head>
<body>
  <div class="header">
    <div>
      <div class="title">Daily Progress Report</div>
      <div class="subtitle">{{ data.project_name }} — {{ data.site_name }}</div>
    </div>
    <div class="code">{{ data.code }}<br/>{{ data.report_date }}</div>
  </div>

  <div class="meta">
    <div class="meta-item"><div class="label">Activities Logged</div><div class="value">{{ data.activity_count }}</div></div>
    <div class="meta-item"><div class="label">Open Issues</div><div class="value">{{ data.open_issue_count }}</div></div>
    <div class="meta-item"><div class="label">Evidence Photos</div><div class="value">{{ data.evidence_count }}</div></div>
    <div class="meta-item"><div class="label">Workers Today</div><div class="value">{{ data.headcount }}</div></div>
  </div>

  <div class="section-title">Activities</div>
  <table>
    <thead><tr><th style="width:16%">Work Type</th><th style="width:34%">Narrative</th>
      <th style="width:14%">Status</th><th style="width:14%">Contractor</th>
      <th style="width:16%">Quantities</th><th style="width:6%">Photos</th></tr></thead>
    <tbody>
      {% for a in data.activities %}
      <tr><td>{{ a.work_type }}</td><td>{{ a.narrative }}</td><td>{{ a.status }}</td>
        <td>{{ a.contractor }}</td><td>{{ a.quantities }}</td><td>{{ a.evidence_count }}</td></tr>
      {% else %}
      <tr><td colspan="6" class="empty">No activities logged for this date.</td></tr>
      {% endfor %}
    </tbody>
  </table>

  <div class="section-title">Site Issues</div>
  <table>
    <thead><tr><th style="width:18%">Type</th><th style="width:12%">Severity</th>
      <th style="width:50%">Narrative</th><th style="width:20%">Status</th></tr></thead>
    <tbody>
      {% for i in data.issues %}
      <tr><td>{{ i.issue_type }}</td>
        <td class="severity-{{ i.severity|lower }}">{{ i.severity }}</td>
        <td>{{ i.narrative }}</td><td>{{ i.status }}</td></tr>
      {% else %}
      <tr><td colspan="4" class="empty">No issues reported for this date.</td></tr>
      {% endfor %}
    </tbody>
  </table>

  <div class="section-title">Labour{% if data.headcount %} (Total cost: {{ data.labour_cost }}){% endif %}</div>
  <table>
    <thead><tr><th style="width:80%">Trade</th><th style="width:20%">Headcount</th></tr></thead>
    <tbody>
      {% for t in data.trades %}
      <tr><td>{{ t.trade }}</td><td>{{ t.headcount }}</td></tr>
      {% else %}
      <tr><td colspan="2" class="empty">No attendance recorded for this date.</td></tr>
      {% endfor %}
    </tbody>
  </table>

  <div class="section-title">Materials</div>
  <table>
    <thead><tr><th style="width:40%">Material</th><th style="width:20%">Received</th>
      <th style="width:20%">Used</th><th style="width:20%">Unit</th></tr></thead>
    <tbody>
      {% for m in data.materials %}
      <tr><td>{{ m.material_name }}</td><td>{{ m.received }}</td><td>{{ m.used }}</td><td>{{ m.unit }}</td></tr>
      {% else %}
      <tr><td colspan="4" class="empty">No material movements recorded for this date.</td></tr>
      {% endfor %}
    </tbody>
  </table>

  <div class="footer">
    <span>Generated by Mesiri</span>
    <span>{{ data.code }}</span>
  </div>
</body></html>
"""

_document_template: Template | None = None


def render_html(data: DprDocumentData) -> str:
    global _document_template
    if _document_template is None:
        from jinja2 import Template

        _document_template = Template(_DOCUMENT_TEMPLATE_SRC)

    return _document_template.render(
        data=data, ink=_INK, sub=_SUB, line=_LINE, accent=_ACCENT, warn=_WARN
    )
