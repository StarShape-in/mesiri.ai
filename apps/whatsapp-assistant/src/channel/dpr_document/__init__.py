"""DPR PDF rendering (#16 Daily Report Generation).

Reuses channel/receipt/'s Jinja2 + Playwright pattern (ADR-D8,
docs/execution/DAILY_REPORTING_PLAN.md) instead of introducing a new PDF
library: data.py shapes the backend-assembled payload into a render-ready
structure, template.py owns the HTML/CSS layout, render.py drives a headless
Chromium page through `page.pdf()` to produce actual PDF bytes.
"""
