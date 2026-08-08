# Project Design Rules & Dashboard Guidelines

## 🎨 MERCON Dashboard Design Specification (Learned from User Design Reference)

Every dashboard, management, and report page in the MERCON Web Dashboard must adhere strictly to the following UI/UX architecture and aesthetic standards:

### 1. Header Layout & Top Bar Actions
- **Scope & Context Selector**: Top-left bar includes scope selector pill (e.g., `[ 🏢 MERCON Logistics ↕ ]`).
- **Page Title & Module Badge**: Page title paired with a soft pastel category badge (e.g., `<Badge className="bg-indigo-50 text-indigo-600 border-indigo-200 font-semibold">Operations Module</Badge>`).
- **Top Bar Actions Group**: Right-aligned action buttons in top header:
  - `Export CSV` (Outline button with download icon)
  - `+ Primary Action` (Solid brand pill button, e.g., `+ New Trip`)
  - `Refresh ↻` (Ghost icon button to manually refetch/refresh query data)

### 2. Instrument-Panel KPI Cards
- **Grid Layout**: 4-column responsive layout (`grid border gap-4`).
- **Card Structure**:
  - **Header Row**: Uppercase tracking-wider muted label on left, icon container on right.
  - **Value Row**: Prominent bold text with color accent matching status.
  - **Trend Subtitle**: Indicator arrow (`→` or `↑`) + descriptive subtitle.
  - **Bottom Area**: Mini shadcn area sparkline chart fading into card bottom edge.

### 3. Toolbar & Control Bar
- **Search Input**: Icon-prefixed search input (`Search ID, customer, driver...`).
- **Icon Dropdowns**: Filter dropdowns with leading icons (`[ 🔀 Status ∨ ]`, `[ 📦 Cargo ∨ ]`, `[ 📅 Date Range ∨ ]`).
- **View Switcher**: Segmented view mode control (`[ ☰ List | 🎛 Grid | 📅 Calendar ]`).

### 4. Data Table Ledger & Empty States
- **Ledger Header Bar**: Title section (`[ 🥞 Trip Ledger ]`) with right-aligned record counter (`42 trips`).
- **Table Headers**: Bold, clean table column headers with optional selection checkbox.
- **Empty State Component**: Centered soft circle icon (`📄`), bold main heading, and helpful secondary message.
