# MERCON Logistics — AI Development Kit Documentation

## Project Overview

MERCON Logistics Services is a B2B logistics SaaS platform designed for fleet operators and professional drivers in the Gulf region. The platform consists of three interconnected products: a Driver mobile app, an Operator mobile app, and a web-based enterprise dashboard. All three products share a unified design system rooted in the same token set, component library, and visual language.

This documentation bundle is the single source of truth for AI coding agents, developers, and designers rebuilding or extending any part of the MERCON platform. Every value referenced in this bundle — hex codes, pixel sizes, font weights, component props, screen names, navigation routes — is derived directly from the production source files.

---

## Design Philosophy

MERCON's design system is built on four pillars:

**Precision over decoration.** Every visual element earns its place. The design eliminates ornamental color, shadow, and animation in favor of purposeful communication. The MERCON Orange (`#E8450F`) is used exclusively for interactive primary actions, active states, and brand moments — never for decoration.

**Hierarchy through contrast.** Dark surfaces (`#1C1C2E`) appear in navigation elements, header cards on detail screens, and stat cards. Light surfaces (`#F5F5F7` background, `#FFFFFF` cards) hold content. This dark-light contrast creates immediate visual hierarchy without relying on complex typography alone.

**Status at a glance.** Logistics operations require instant recognition of trip, vehicle, and document states. The status system uses a consistent five-color semantic palette mapped to business states. StatusBadge components auto-resolve colors from status strings so no developer ever manually selects a status color.

**Operational density.** Operator and dashboard screens are information-dense. Cards show multiple data points in a compact layout. KPI chips, progress bars, and timeline steps all compress meaningful data into minimal screen space.

---

## Visual Language

- **Primary color:** MERCON Orange `#E8450F` — used for primary buttons, active tab indicators, FAB borders, progress fills, and brand moments
- **Dark surface:** `#1C1C2E` — used for navigation pill background, header cards, stat cards, and the DarkCard component
- **Page background:** `#F5F5F7` — light gray used as the global screen background
- **Card surface:** `#FFFFFF` with `rgba(0,0,0,0.07)` border — used for all white content cards
- **Font family:** Plus Jakarta Sans — used for all text in the product; monospace fallback for IDs and codes
- **Border radius scale:** 4 / 8 / 12 / 16 / 20 / 24 / 32 / 9999 — cards use `Radius['2xl']` (24), buttons use `Radius.xl` (20), pills use `Radius.full` (9999)
- **Spacing grid:** 8pt base grid — xs:4, sm:8, md:12, base:16, lg:20, xl:24, 2xl:32, 3xl:40, 4xl:48, 5xl:64

---

## Target Users

**Drivers (Driver App):** Professional long-haul truck drivers operating on Saudi Arabian freight routes. They use the app while stationed or at rest stops. The app must be legible in bright outdoor conditions, support Arabic names and SAR currency, and minimize cognitive load during active trips. Primary language: Arabic with English IDs.

**Fleet Operators (Operator App + Web Dashboard):** Operations managers and dispatch coordinators who monitor fleets of 5–100+ trucks. They manage trips, drivers, vehicles, invoices, and customers. The Operator App handles field use; the web dashboard handles desktop office workflows. Both require dense information presentation and fast status scanning.

---

## How This Documentation Is Organized

| File | Purpose |
|------|---------|
| `README.md` | Project overview, onboarding, folder structure |
| `design.md` | Complete design language specification |
| `components.md` | Every component with all variants, props, states |
| `screens.md` | Every screen documented with purpose and data |
| `flows.md` | User flows with Mermaid diagrams |
| `animations.md` | All motion specifications |
| `accessibility.md` | WCAG 2.1 AA compliance guidelines |
| `developer-guide.md` | Folder structure, naming, code organization |
| `implementation-guide.md` | 12-phase build order |
| `architecture.md` | Component hierarchy and system architecture |
| `assets.md` | Icons, illustrations, logos, SVG specs |
| `api-contracts.md` | Data models and API response shapes |
| `tokens.json` | Machine-readable design token export |
| `component-map.json` | Component inventory as structured JSON |
| `screen-map.json` | Screen inventory as structured JSON |
| `assets-manifest.json` | Asset inventory as structured JSON |
| `navigation-map.json` | Route and navigation structure as JSON |
| `design-checklist.md` | QA verification checklist |
| `ai-rules.md` | Strict rules for AI agents |

---

## Implementation Order

1. **Tokens** — implement `tokens.ts` as the foundation. No component should be written before tokens exist.
2. **Typography components** — implement `Typography.tsx` helpers (Heading, Title, Body, Caption, Overline, Mono)
3. **Atom components** — Badge family, Avatar, StatusBadge
4. **Input components** — Input, SearchInput
5. **Card components** — Card, DarkCard
6. **Button** — all 6 variants × 3 sizes
7. **Navigation** — DriverBottomNav, OperatorBottomNav
8. **Driver screens** — in the order listed in `screens.md`
9. **Operator screens** — in the order listed in `screens.md`
10. **Web dashboard** — sidebar layout, then individual pages
11. **Flows and animations** — apply motion after layout is confirmed
12. **Accessibility audit** — apply WCAG 2.1 AA corrections

---

## Developer Onboarding

**Prerequisites:**
- Node.js 18+
- React Native 0.73+ (or Expo SDK 50+)
- `lucide-react-native` for icons
- `@react-navigation/native` + `@react-navigation/bottom-tabs` + `@react-navigation/stack`
- Plus Jakarta Sans font loaded via `expo-font` or equivalent

**Folder structure (React Native):**
```
react-native/
  theme/
    tokens.ts           ← Single source of truth for all design values
  components/
    Button.tsx
    Badge.tsx
    Card.tsx
    Input.tsx
    Avatar.tsx
    Typography.tsx
    index.ts            ← Barrel export
  navigation/
    DriverBottomNav.tsx
    OperatorBottomNav.tsx
  screens/
    driver/             ← 16 driver screens
    operator/           ← 41 operator screens
  index.ts              ← Root barrel export
```

**Getting started:**
1. Clone the repository
2. `npm install` or `yarn install`
3. Load Plus Jakarta Sans font before the app renders
4. All imports should go through `react-native/index.ts`
5. Never import from component files directly — use the barrel export

---

## AI Agent Onboarding

If you are an AI coding agent working on this codebase:

1. Read `ai-rules.md` first and follow every rule without exception
2. Read `tokens.json` to understand the complete token vocabulary
3. Read `component-map.json` to understand what components exist and their props
4. Read `screen-map.json` to understand what screens exist and what they contain
5. Never hardcode a color, spacing value, font size, or border radius — always use tokens
6. Never create a new button variant, badge color, or typography style that does not exist in the token system
7. Every component must render identically on iOS and Android
8. All status colors must resolve through `getStatusColors()` — never manually assign status colors

---

## Dependencies

```json
{
  "react-native": ">=0.73",
  "react": ">=18",
  "lucide-react-native": "latest",
  "@react-navigation/native": "^6",
  "@react-navigation/bottom-tabs": "^6",
  "@react-navigation/stack": "^6",
  "react-native-safe-area-context": "latest",
  "react-native-screens": "latest",
  "expo-font": "latest"
}
```

---

## Recommended Workflow

**For new screens:** Check `screen-map.json` → identify components needed → check `component-map.json` → build using only documented components and tokens.

**For new components:** Check `components.md` first to confirm the component does not already exist. If it does not, follow the token-first pattern established in the existing components. Document the new component in `components.md` and `component-map.json`.

**For bug fixes:** Check `design-checklist.md` to confirm the issue before fixing. Reference `tokens.json` for correct values.

**For AI agents:** Always read `ai-rules.md` before making any changes to any file in this codebase.
