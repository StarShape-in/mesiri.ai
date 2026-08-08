# MERCON — Project Progress (Living Status)

**This is the single source of truth for "where is the project."**
Last updated: **2026-08-08** (**Driver list page action buttons updated to match Trips section style**: `frontend/web-dashboard/src/pages/drivers/DriverListPage.tsx` replaced the dropdown menu (`Actions ▾`) in the Driver Roster Ledger table and the single "View Profile" button on grid cards with direct, responsive icon action buttons (View Profile in blue, Quick Status Update in emerald, Compliance Docs in purple, Edit Driver in amber, and Delete in rose) styled with tooltips and hover backgrounds matching `TripListPage.tsx`). Earlier the same day: (**site-wide `--font-mono` set to JetBrains Mono**: `frontend/web-dashboard` added `@fontsource-variable/jetbrains-mono` (self-hosted, matching the existing `@fontsource-variable/geist`/`inter` pattern) and declared `--font-mono` in `index.css`'s `@theme inline` block, which previously had no override — Tailwind's `font-mono` utility (used across 41 files for plate numbers, ref IDs, timestamps, currency) was falling back to the default OS-monospace stack. `--font-sans` (Geist-based) and the separate "Geist Mono Numbers" digit-only `@font-face` hack were left untouched — out of scope for this change. Verified: `font-mono` utility now resolves to `'JetBrains Mono Variable'` via computed styles, the woff2 loads with a 200 from `node_modules` locally (self-hosted, no CDN), and both `tsc --noEmit` and a full `vite build` pass. Not checked past the login screen in-browser (dashboard requires auth). Earlier the same day: **Active Freight Trips Carousel hover effects toned down** — the lift/glow/gradient-overlay hover animations added in the carousel rebuild below (translate-y lift, colored shadow glow, scale-in accent rail, gradient map overlay, rotating gauge icon, sliding CTA arrow, animated ping dot, gradient corridor/progress fills) were replaced with a plain border-color + `shadow-sm` transition per owner feedback ("that's AI slop"), and the card background moved from `#FAFAFA` to white with a visible border instead of a faint ring, matching the app's existing restrained style. Earlier the same day: **Active Freight Trips Carousel rebuilt on shadcn**: `components/trips/TripCardSwiper.tsx` (dashboard) moved off its hand-rolled `overflow-x-auto` + scroll-listener carousel onto the shadcn **`Carousel`** primitive (`components/ui/carousel.tsx`, added — embla-carousel-react, already a dependency), gaining drag, arrow-key nav, snap-accurate index tracking and clickable dot indicators wired through a new `useCarousel()`-consuming `CarouselToolbar` in the card header (`CardAction` slot). Three more shadcn primitives added to support it: **`avatar.tsx`** and **`hover-card.tsx`** (both on `@base-ui/react`, matching the repo's `base-nova` style — hover-card wraps Base UI's `PreviewCard`) and **`skeleton.tsx`**. Each trip card was redesigned: driver tile is now an `Avatar` + `HoverCard` (phone/plate/cargo on hover), vehicle tile a `Tooltip`, the route corridor uses `Separator` with pin/flag icons, the micro-map gained a gradient hover overlay showing km-remaining + ETA, and progress now shows distance done/left. Hover/focus/active animations are shadcn-idiomatic throughout (lift + ring + shadow on the card, a scale-in accent rail, icon transforms, animated dot width) and cards are keyboard-focusable (`Enter`/`Space` to open). Also fixed a latent bug: the progress bar's `[&>div]` selector was coloring the **track** rather than the indicator, so every bar rendered visually full — it now targets `[data-slot=progress-indicator]` with a gradient fill. Verified by `tsc --noEmit` and a full `vite build`; not verified in-browser (the dashboard is behind login). Earlier: **Trip creation: "assign driver/vehicle later" added**: `POST /trips` no longer requires `driver_id`/`vehicle_id` — a trip created without one or both now lands in `Draft` status instead of `Dispatched` (driver/vehicle claiming and the assignment notification are skipped for whichever is missing). `/trips/:id/dispatch` (`dispatchTrip`) reworked to accept either field independently rather than requiring both, so a Draft trip can have its driver and vehicle assigned in separate calls; it only flips the trip to `Dispatched` once both end up set. `updateTripStatus` gained a guard rejecting a direct Draft→Dispatched status change when the trip still has no driver or vehicle (that path must go through `dispatchTrip`, which does the atomic Available→OnTrip claim) — web's `TripDetailsPage.tsx` mirrors this by hiding the "Mark Dispatched" quick action until both are assigned. Web changes: `CreateTripPage.tsx` (`/trips/new`) step 2 gained "Assign driver later"/"Assign vehicle later" checkboxes that disable the respective picker and relax the step/submit validation; `TripDetailsPage.tsx`'s driver/vehicle cards now show an inline assign-now picker (calling the reworked dispatch endpoint) when a Draft trip is missing one; `Combobox` (`components/ui/combobox.tsx`) gained a `disabled` prop to support the checkbox-disables-picker interaction. Not yet run against a live server for E2E verification — a concurrent session's in-progress `hazmat_flag` removal (`schema.prisma`) had the local API mid-edit and returning 500s on login at the time; both `backend/api-server` and `frontend/web-dashboard` typecheck clean (`tsc --noEmit` / `tsc -b`). **Hazmat removed entirely from the project**: `hazmat_flag` dropped from `Trip` in `schema.prisma` (production data loss on next deploy — owner confirmed), the zod schema, `tripController.createTrip`, both web (`tripService.ts`, `CreateTripPage.tsx`, `TripListPage.tsx` badge + KPI breakdown, `exportUtils.ts` CSV column) and mobile (`operator.ts` types, `TripDetailsScreen.tsx` cargo row) call sites, and the unrelated static "Hazmat Clearance" placeholder badge on `RateCardDetailsPage.tsx`. The IN-TRANSIT KPI's on-schedule/delayed breakdown had been (mis)computed from `hazmat_flag` as a stand-in for "delayed" — there is no real delay signal at the trip level (only per-stop `delay_reason`), so it now reads on-schedule = active-in-transit minus stopped, delayed = 0, until a real delayed-trip metric is built. Earlier the same day: web dashboard **removed the small uppercase "Module" badges next to page titles** — e.g. "Tariff Module" on Rate Cards, "Operations Module" on Trips, "Fleet Module" on Drivers/Vehicles/Maintenance, "Finance Module" on Invoices/Payment Status, "Commercial Module" on Customers, "Platform Module" on User Management, "System Administration" on Settings, "Dashboard Overview" on the dashboard greeting, "Fleet Roster" on Vehicles, "Operations Alert System" on Notifications — across 10 pages, per owner request; the `<h1>` title and the "Scope: ..." subtitle line beneath it were left untouched. Earlier the same day: web dashboard **fixed User Management's missing header/action buttons**: `DashboardLayout` never actually renders its `pageTitle`/`pageSub`/`actions` props — they're accepted but unused in the component body, so any page still passing them (only `UserManagementPage` did) silently got no page header and no action buttons at all, regardless of role. Reworked the page to render its own header row + Admin-only "Add Driver"/"Invite User" buttons inline, matching the pattern every other list page already uses (`DriverListPage`, `CustomerListPage`, etc: icon + title + badge + subtitle row, followed by `Button`s, all inside `children` rather than layout props). Also tightened permissions per owner request: Operators now see Admin/Operator rows only (no Drivers) and are view-only (no create/edit/delete/Add Driver); only Admin gets those actions and the Drivers rows. Backend `userRoutes.ts` split so `GET /users` allows Admin+Operator but `POST/PUT/DELETE /users` require Admin. Verified both roles by injecting a synthetic session client-side (no real credentials used) and reading the rendered page. Earlier the same day: added **`.github/workflows/ci.yml`**: a new hosted-runner (`ubuntu-latest`) CI workflow that runs on every PR into `main` and every push to a non-`main` branch — `npm ci`, `npm run lint -w @mercon/web-dashboard` (oxlint), then `npm run build` (build:types → api-server `tsc` → web-dashboard `tsc -b && vite build`), so a broken build/typecheck is caught before merge instead of failing on the self-hosted deploy runner. This is deliberately a separate workflow from `ci-cd.yml`, not a split of it: `ci-cd.yml` stays a single job because its steps are an ordered, stateful deploy sequence (containers must be healthy before nginx reloads) with no parallelism to gain on a single self-hosted runner — splitting *that* would only add fragile cross-workflow ordering. `ci.yml` is unrelated in trigger (PR/branch, not `push: main`) and runner (hosted, no secrets/prod access needed) so it's a genuinely separate concern, not a job split. Earlier the same day: backend **fixed a brief production outage**: the `ilan` seed commit below had hardcoded `phone: '+966500000003'`, which collided with an existing user's phone (unique constraint) already in the hosted DB; the container's startup chain is `prisma db push && seed.ts && node dist/index.js`, so the thrown seed error meant `node dist/index.js` never ran and `mercon.tech/api/*` 502'd entirely until the fix (drop the hardcoded phone — it's optional on `User`) deployed. Also added a permanent diagnostic step to `ci-cd.yml` that prints `mercon-api` container logs after every deploy so a startup crash is visible in the Actions run instead of a bare 502. Verified: `/api/health` 200 and `POST /api/auth/login` for `ilan`/`ilan1234` returns a valid token with role Admin. Earlier the same day: backend **`prisma/seed.ts` now also upserts a third canonical account, `ilan` (role Admin)**, added at the owner's explicit request alongside the existing `admin`/`operator` upserts — idempotent, own bcrypt hash, existing accounts still never touched. Earlier the same day: web dashboard **`/trips/new` (Create Trip wizard) restyled to match `/drivers/new` and `/vehicles/new`**: the 3-step wizard structure is unchanged (Customer → Driver/Vehicle assignment → Route/geofencing, the last step embeds `LocationPickerMap` so it wasn't collapsed into the single-viewport 2-column layout used on the other two pages), but every hardcoded `slate-*`/`indigo-*`/`rose-*` class was swapped for theme tokens, the step-manifest strip's boxed indigo icon circles were removed in favor of bare icons (matching the orange bare-icon convention already applied to page headers elsewhere), and the error banner now uses the shared `Alert` primitive instead of a hand-rolled rose div. Earlier the same day: web dashboard **User Management (`/settings/users`) opened up to Operator** (previously Admin-only) and turned into a combined "all platform users" view: it now also lists Drivers by querying `/drivers` alongside `/users`, shown read-only (a "View" action links to `/drivers/:id`) since Driver accounts have no login and are still only created/edited through the Drivers module; an "Add Driver" button links to `/drivers/new`. Backend `userRoutes.ts` changed from `authorizeRoles('Admin')` to `authorizeRoles('Admin', 'Operator')` on all `/users` routes; `createUserBody`/`updateUserBody` still restrict `role` to `Admin`/`Operator` only, so Driver-role web accounts remain non-creatable via this form, per the existing Phase-1 rule. `CLAUDE.md`'s "Who uses which app" table updated to match. Earlier the same day: web dashboard **`/vehicles/new` (Add Vehicle) redesigned to match `/drivers/new`**: same 2-column shadcn layout — form card (asset identifier / payload & telematics / optional trailer, separated by `Separator`s) beside a sticky "Registration summary" card with a live 4-item requirements checklist (plate, tractor capacity, trailer config, telematics); the old horizontal preview-strip + narrow single-column card + hardcoded slate/indigo classes were replaced with theme tokens and the shared `Alert` primitive for errors. Earlier the same day: **`/drivers/new` (Add Driver) redesigned** the same way: the full-width preview strip + narrow stacked form became a 2-column shadcn layout — form card (personal profile / commercial licence, separated by `Separator`) beside a sticky "Onboarding summary" card with a live 4-item requirements checklist, so the whole page fits one viewport with no scrolling; errors now render in the new shadcn `Alert` primitive (`components/ui/alert.tsx`, added), the page is a real `<form>` with a submit button, hardcoded slate/indigo classes gave way to theme tokens, a triple Ctrl+Enter submit binding (window listener + two `Btn` shortcuts, all firing the mutation) was reduced to one, and inputs/labels/headings were later sized up a notch (h-11 inputs, text-sm labels) for readability — both pages share that larger sizing. Also that day: **hosted demo-data workflow added**: `.github/workflows/demo-data.yml` loads the ~3,100-trip Delay Report demo dataset into the hosted database and removes it again — `workflow_dispatch` only, two actions (`seed`/`purge`), a typed `SEED`/`PURGE` confirmation checked before anything runs, and a `demo-data` GitHub Environment for a required reviewer. Both scripts run via `docker exec` inside the deployed `mercon-api` container (verified the image ships `scripts/` and `ts-node` — it already runs `npx ts-node prisma/seed.ts` at startup), and `DEMO_RESET` is never passed, so the seeder's destructive path is unreachable from CI. Row counts print before and after, tagged vs total. `ci-cd.yml`, `prisma/seed.ts` and `docker-compose.yml` untouched. Not yet run — the self-hosted runner is the only thing that can reach the production database. Previous session, 2026-08-05: mobile **operator Customers screen rebuilt** on `features/customers` at `/operator/customers` (More → Customers): KPI rail, server-side search/filter, sort, infinite scroll, per-customer trips/revenue/rate-card aggregated from `/trips`+`/invoices`+`/rate-cards`, and a role-gated overflow menu with optimistic suspend/delete; generic `SortDropdown` + `useDebouncedValue` extracted to `shared/`. Also merged in, same day: the **Delay Reporting module** built end to end — a `/reports/delays` page with three views behind one filter bar: the delay log (one row per late arrival, click-through to the trip), an on-time % grid switchable by route/driver/company/truck, and an analysis tab with KPIs, an hours-lost trend and four leaderboards, all at any period from day to year with a delta against the preceding window. Backing it: `TripStop.actual_departure`, `location_name`, and `delay_reason`/`delay_note`/`delay_logged_by`/`delay_logged_at` + a `DelayReason` enum; three `/reports/delays*` endpoints; and an operator alert that fires the moment a stop is reached 30+ min late. **Two real data bugs fixed underneath it**: the mobile/geofence status path never stamped `actual_arrival` at all (and dropoff arrival was backfilled at completion, dating every delivery to when its paperwork finished), so the database could not tell "arrived 2h late" from "arrived on time and waited 2h to unload"; and the mobile operator's Create Trip screen sent no planned times, so every trip booked from a phone was invisible to delay reporting. Reason capture is operator-only by design — drivers already report causes in the WhatsApp group. Verified end to end over real HTTP against a live Postgres, plus a browser walkthrough of the report page on a seeded dataset. Earlier the same day: mobile **operator Home + Drivers list screens rebuilt** on a new `features/dashboard` and `features/drivers` architecture — NativeWind + TanStack Query added to the mobile app for the first time (babel/metro/tailwind config, `QueryClientProvider` in root layout); Home is now AppHeader/context chips/search/scanner, two `DashboardMetricCard`s (Active Trips, Delayed Deliveries), an `ActiveVehiclesSection` carousel (driver+route+status per active trip), and a `DocumentExpirySection` (replaces the old Fleet Utilization block) with real expiring-document counts + a scoped All/Vehicles/Drivers/Company list; Drivers list gained two dark KPI tiles, search/status-filter/sort, and backend-paginated infinite scroll. Then: mobile **operator Driver Details screen** — new `features/drivers` screen at `/operator/driver-details?id=` with profile/statistics, assigned vehicle, contact + licence info, documents, current assignment, performance summary and call/message actions, built on a layered api→services→hooks stack with React Query caching, pull-to-refresh and optimistic status updates; the driver list now taps through to it. Earlier the same day: web dashboard **mobile responsiveness pass**: the fixed 220px sidebar became an off-canvas drawer below `lg` driven by a header hamburger, the overflowing 8-item route pill bar is now desktop-only with Quick Create promoted to a header `+`, `DataTable`/`dialog.tsx`/`PageTitle` made phone-friendly, and page containers + stray fixed grids given mobile-first breakpoints. Also fixed a **pre-existing syntax error on `main`** — `handleUpdateStatus` in `DriverListPage.tsx` was missing its closing `};`, which made `tsc -b` fail and would have broken the Docker build/deploy. Previous session, 2026-08-04: fleet data onboarding: Excel export on the Drivers/Vehicles list pages now includes the driver's assigned vehicle plate and the vehicle's assigned driver — backend `getDrivers`/`getVehicles` now `include` the active trip + its vehicle/driver; styled `.xlsx` bulk-entry templates + `docs/MERCON_Fleet_Import_Guide.md` reworked to match those columns. Note: the templates are for **manual collection today — there is no backend import endpoint yet**. Previous session, 2026-08-02: mobile operator UI-kit consistency pass across all 8 operator screens + fixed a duplicate-bottom-nav bug; added real trip lifecycle actions (pickup arrive/verify, delivery verify, replace driver, cancel) to `TripDetailsScreen`; added Driver/Vehicle edit screens; added invoice "Mark as Paid"; added full Customers screen (list/search/create/edit); added an `Operator` "More" hub screen — fixed a real navigation gap where Vehicles/Invoices/VehicleRenewals were only reachable via deep link, not from the UI) · Owner: Hysam (solo dev + AI) · Deadline: ~1 month from July 2026

> ⚠️ **Keep this file honest.** It is written from reading the actual code, not the
> docs (the `docs/` folder describes the *planned* product and overstates progress).
> See the **[Update protocol](#update-protocol)** at the bottom — this file must be
> updated in the same change as any code/schema/endpoint/screen change.

---

## 1. TL;DR — where we are

| Area | Status | Done |
|---|---|---|
| **Backend API** | ✅ Working, deployed at mercon.tech | ~90% |
| **Web dashboard** (Admin/Operator) | ✅ Done, all pages on real data | ~95% |
| **Mobile app** (Driver + Operator) | 🔄 Driver side ~done (nav + full trip flow + all core screens); operator side wired with real trip lifecycle actions (dispatch→pickup→delivery→complete, replace driver, cancel), Driver/Vehicle edit, Invoice mark-paid, and a new Customers screen (list/create/edit); a proper "More" hub now makes Vehicles/Invoices/Customers/Renewals reachable in-app (previously only via deep link); only secondary Replacement/Splash screens left static; live GPS pending | ~76% |
| **Live GPS tracking** (driver → web) | 🔄 Foreground streaming wired (socket emit); background + device verification pending | ~60% |
| **Delay reporting** (log + on-time grid + analysis) | ✅ Built, verified end to end | ~90% |
| **Testing / builds / handover** | ❌ Not started (no real-phone run yet) | 0% |

**One-line status:** Backend and web are basically finished. Trips assigned a driver + vehicle at
creation are auto-dispatched immediately (driver notified); either can now be left for "assign later",
landing the trip in `Draft` until both are filled in via the dispatch endpoint. On **mobile**, the whole **driver
side is real** — navigation, a straight-through trip flow (photo → live map with GPS auto-arrival →
POD → done), notifications, profile, documents, vehicle, emergency, and foreground **live GPS**
streaming. The **operator side is now navigable and wired**: Admin logs into the same operator nav
as Operator, `/operator/{trips,trip-details,create-trip,drivers,vehicles,invoices,vehicle-renewals}`
routes exist, the bottom nav + FAB actually go somewhere, trip cards tap through to a real
trip-details screen (real timeline/cargo/driver/vehicle, call-driver, "coming soon" for live
tracking/edit), Create Trip posts to `POST /trips` against real customers/available drivers/vehicles,
and Vehicle Renewals (reachable from the Home "docs expiring" alert) shows real expiring vehicle
documents. For **owner onboarding**, styled drivers/vehicles Excel templates + a field-mapping guide
exist and the web list pages now export the same columns (incl. assigned vehicle/driver) — but
**there is no import endpoint yet**, so a filled workbook still has to be entered by hand.
Remaining: bulk-import endpoint + UI, GPS background hardening + device verification, then
real-phone testing + release builds.

---

## 2. ✅ Completed

### Backend (`backend/api-server`)
| Piece | State |
|---|---|
| 18 controllers (auth, users, drivers, vehicles, customers, trips, invoices, rate cards, documents, maintenance, notifications, reports, tracking, uploads + 2 mobile) | ✅ real DB logic |
| Prisma schema (11 models, 10 enums), PostgreSQL, idempotent seed (admin + operator accounts only — see §6, fake demo data seeding was added and removed same day) | ✅ (2026-07-29) |
| JWT auth + **RBAC** `authorizeRoles` on all feature routes | ✅ (`ddbe688`) |
| Exactly 3 roles: Admin / Operator / Driver (Prisma enum + shared-types) | ✅ locked |
| Live GPS relay (Socket.io: receives `driver:location_update`, broadcasts to web) | ✅ |
| ICCES vehicle-tracker polling (3 background jobs) | ✅ (creds not provided yet) |
| File uploads (photos, documents) | ✅ |
| Zod request validation on write + list routes | ✅ (`79d4cd4`) |
| `POST /trips` requires `driver_id` + `vehicle_id` (no driverless trips); creates directly as `Dispatched` (same availability checks + `OnTrip` flip + driver notification as `dispatchTrip`), 400s if driver/vehicle isn't `Available` | ✅ (2026-07-28) |
| Structured logging (Pino), collision-safe reference IDs | ✅ (`d816736`, `f32cbca`) |
| `JWT_SECRET` rotated → GitHub Actions secret, leaked fallback removed | ✅ (2026-07-12) |
| Driver fixes: validate `PATCH /drivers/:id` (fixes "Failed to update"), free phone number on delete so it can be reused | ✅ (`a217c59`, `029cee7`) |

### Delay reporting (backend + web) — new 2026-08-05
| Piece | State |
|---|---|
| `TripStop.actual_departure` + `stampStopTransition()` owning the stop clock; every status path (web generic, pickupArrive, pickupVerify, mobile/geofence, completion) stamps arrival/departure inside its transaction | ✅ |
| Fixed: mobile/geofence path never wrote `actual_arrival`; dropoff arrival no longer backfilled at completion (it dated deliveries to when paperwork finished) | ✅ |
| Fixed: mobile operator Create Trip sent no `planned_arrival`, so phone-booked trips could never count as late | ✅ |
| `TripStop.location_name` + capture in both create-trip forms (web picker auto-fills from its existing Nominatim search, editable) | ✅ |
| `DelayReason` enum + `delay_reason`/`delay_note`/`delay_logged_by`/`delay_logged_at`; `PATCH /trips/:id/stops/:stopId/delay` (operator-only, re-loggable) | ✅ |
| Operator alert broadcast to every active Admin + Operator when an arrival lands 30+ min late; fires post-commit, once per stop | ✅ |
| `GET /reports/delays`, `/delays/grid`, `/delays/analysis` — shared filters (range, customer, driver, vehicle, reason); grid switchable by route/driver/company/vehicle; analysis at day→year granularity with previous-window deltas | ✅ |
| `/reports/delays` page: log (click-through to trip), on-time grid, analysis (KPIs, trend, 4 leaderboards), CSV export | ✅ |
| Reason picker on `TripDetailsPage` for any stop over the threshold | ✅ |
| Demo dataset for exercising the report: `scripts/seed-demo-local.ts` (~3,100 trips / 2 years, patterned so the report has real findings) + `scripts/demo-purge.ts` (deletes only rows tagged with the marker in `created_by`). Wiping requires `DEMO_RESET=yes` explicitly — never inferred from the hostname, since production's `postgres-db` compose service name is identical on a laptop (`455ff5b`) | ✅ |
| `.github/workflows/demo-data.yml` — `workflow_dispatch`-only seed/purge of the **hosted** database, gated on a typed `SEED`/`PURGE` confirmation and the `demo-data` GitHub Environment; runs both scripts via `docker exec` inside `mercon-api`, never passes `DEMO_RESET`, prints before/after row counts. Docs: `docs/LOCAL_DEMO.md` | ✅ (2026-08-07, unrun — needs the self-hosted runner) |

**Verification:** end-to-end over real HTTP against a live Postgres — operator creates a trip,
driver runs it late through the mobile endpoints, operators get alerted, an operator logs the
reason, and every report view reflects it; plus invoice generation and driver/vehicle release
confirmed unbroken, and a driver token confirmed rejected from the operator reports. The report
page was also walked in a real browser against a seeded dataset (3 companies, 4 routes, 25 trips),
which caught two render bugs a type-check could not (percentage-height bars collapsing to zero,
and the ﷼ glyph reordering beside digits).

**Not covered:** no independent GPS cross-check of departure times — the client's reference sheet
compares three sources, MERCON has one (the driver's app) until ICCES credentials arrive. Waiting
time is measured and reported but never billed automatically. Alerts reach open dashboards, not
locked phones (needs push, still deferred). History starts at deploy: older trips have no location
names, unreliable arrivals and no reasons, and cannot be backfilled.

### Web dashboard (`frontend/web-dashboard`) — Admin + Operator
| Piece | State |
|---|---|
| 44 pages, all wired to the real API (no mock data left) | ✅ |
| 11 service modules (auth, customer, driver, invoice, notification, rateCard, reports, trip, user, vehicle, document) | ✅ |
| Live trip tracking over WebSocket | ✅ |
| Role-gated pages (`RequireRole`) + User Management (Admin + Operator; lists Admin/Operator web users plus Drivers read-only, "Add Driver" links to `/drivers/new`) | ✅ |
| Operator-driven password reset + "notify my operator" flow | ✅ |
| Debounced server-side search across list pages | ✅ (`0546e0f`) |
| Brand/semantic color tokens as Tailwind utilities | ✅ (`12fa35b`) |
| Site-wide semi-curved corners (replaced 224 `rounded-none` overrides → `rounded-lg`; shadcn primitives use idiomatic radii) | ✅ |
| Create Trip: driver + vehicle now required (no "leave unassigned"); pickup/dropoff lat/lng number inputs replaced with `LocationPickerMap` (address search via OpenStreetMap Nominatim + click/drag pin on a Leaflet map, no API key) | ✅ (2026-07-28) |
| Login page redesign: full-bleed logistics background image (`login-bg.png`), no center divider, logo pinned top-right, centered "Welcome back" heading + boxed sign-in card | ✅ (PR #2 → `a09fa8d`) |
| Fleet Excel **export**: Drivers/Vehicles list pages export `.xls` (styled sheet, replaces the old CSV export) including the driver's **assigned vehicle plate** and the vehicle's **assigned driver**, resolved from the active trip (`Dispatched`/`AtPickup`/`InTransit`/`AtDelivery`) that `getDrivers`/`getVehicles` now `include` | ✅ (2026-08-04, `234d191`) |
| **Mobile responsiveness**: sidebar is now an off-canvas drawer below `lg` (backdrop, Esc/route-change/nav-tap close, body-scroll lock) with a hamburger in the header; the 8-item route pill bar is hidden below `lg` and Quick Create moved to a header `+` button; `DataTable` scrolls horizontally (`min-w-[720px]`) with a responsive toolbar/footer; `dialog.tsx` gets viewport margin + `max-h-[90dvh]` scroll so every modal fits a phone; page containers `px-4 sm:px-6`; unprefixed `grid-cols-2/3/4` given mobile-first breakpoints | ✅ (2026-08-05) |

### Mobile app (`frontend/mobile-app/mercon-app`) — Expo, Driver + Operator
| Piece | State |
|---|---|
| App entry fixed (`expo-router/entry`), 24 screens type-check (tsc 349→0) | ✅ |
| Runtime packages installed (axios, socket.io-client, expo-secure-store, expo-location, expo-image-picker) | ✅ |
| API client (JWT interceptor) + SecureStore auth context (auto-login) | ✅ |
| **Unified login** (single form, auto-detects driver vs operator by credentials — no mode toggle) + **role routing** (`app/index.tsx`); redesigned UI (real logo, hero background image `login-hero.png`, simplified Username/Password inputs — driver: phone/license, no welcome heading, centered compact card, notify-operator button below card) | ✅ (`c3c83cf`) |
| Driver **Home**: real current trip, status updates, cargo + POD photos (camera), photo-gated status | ✅ (`fee951d`, `dd184c1`) |
| Bottom nav redesign (driver + operator): lucide icons, orange "capsule" active indicator (springs in on page switch), sized like a standard app bar, dropped lower | ✅ |
| Profile header redesign: larger avatar left, name + driver ID + status badge stacked to its right | ✅ |
| **App-wide emoji → lucide icon sweep**: every driver + operator screen, shared `SearchInput`, and the `docIcon`/`notificationIcon` helpers now use lucide icons (no emojis anywhere in the UI) | ✅ |
| Active-trip card redesign (Home): fixed edge-clipping (DarkCard padding) + route timeline, divider, tidy meta row | ✅ |
| Home screen: trip section (empty banner or active-trip card) now centers vertically in the remaining page space; full-screen faded truck/route background image (`home-bg.png`) behind header + content | ✅ |
| Photo upload: camera **or** gallery (`choosePhoto` chooser) on pickup/delivery/home; pickup checklist removed, larger confirm button | ✅ |
| **Operator Home screen rebuilt** (`features/dashboard`): first use of **NativeWind** (Tailwind for RN) and **TanStack Query** in the mobile app — `babel.config.js`/`metro.config.js`/`tailwind.config.js` added, `global.css` wired through `_layout.tsx`, root wrapped in `QueryClientProvider`. Screen: `AppHeader` + `ContextSelector` (role chip) + `SearchBar`/`ScannerButton`, two `DashboardMetricCard`s (Active Trips / Delayed Deliveries — "delayed" derived from `planned_end` vs. now, no backend status for it), `ActiveVehiclesSection` (snapping `FlatList` carousel of `VehicleCard`s — driver, illustrated `RoutePreview`, truck ID/model/capacity, a derived `VehicleCardStatus` pill), and `DocumentExpirySection` (**replaces** the old Fleet Utilization block — summary counts + All/Vehicles/Drivers/Company-scoped list of real documents with an `expiry_date`, "Company" meaning "not a Driver/Vehicle doc" since the backend has no Company entity). Layered api → services → hooks throughout; presentation components never call the API | ✅ (2026-08-05) |
| **Operator Drivers list screen rebuilt** (`features/drivers`): two dark `DriverStatCard` KPI tiles (Total Drivers/On Trip, with available/offline as captions), inline search, status `FilterBottomSheet`, `SortDropdown` (name/newest/most-trips/available/online — all client-side, since `GET /drivers` has no `sort_by` support), backend-paginated infinite-scroll `FlatList` of `DriverCard`s (avatar+status dot, status badge, assigned vehicle + coarse "En Route"/"Unknown" location, rating **"—"** and trip count from `GET /reports/drivers` joined client-side — no rating field exists in the schema, never fabricated). `useDrivers`/`useDriverStats`/`useDriverSearch`/`useDriverFilters`/`useDriverSorting` hooks | ✅ (2026-08-05) |
| **Operator Customers screen rebuilt** (`features/customers`, route `/operator/customers`, reached from More → Customers): dark KPI rail (total customers, active rate cards, trips this month, pending bills), server-side search + active/inactive filter, client-side sort, backend-paginated infinite scroll, and per-customer trips/revenue/outstanding/rate-card derived by aggregating `/trips`, `/invoices` and `/rate-cards` once each (the customer table joins nothing, so this avoids an N+1). Overflow menu gates Edit/Suspend/Delete off the authenticated role; suspend + delete are optimistic across every cached page with rollback. Also extracted a generic `SortDropdown` and `useDebouncedValue` into `shared/` (drivers now use both instead of near-duplicates), and `create-trip` accepts a `customerId` param so "Create Trip" pre-selects the customer | ✅ (2026-08-05) |
| **Operator Driver Details screen** (`features/drivers`, route `/operator/driver-details?id=`): profile card + statistics, assigned vehicle (dark card, from the active trip), contact/licence info, horizontal documents list with derived Valid/Expires Soon/Expired/Pending Renewal status, current assignment, performance summary, call/message actions. Layered api → services → hooks (`useDriver`, `useDriverDocuments`, `useDriverPerformance`, `useDriverAssignment`, `useDriverActions`) with React Query caching, pull-to-refresh, 60s auto-refresh and optimistic status updates; presentation components never call the API. Driver list now taps through to it instead of the edit form | ✅ (2026-08-05) |
| Driver trip flow now goes straight through, no detour back to Home: pickup cargo photo → real live map (`react-native-maps` + OSM tiles, no API key) with the dropoff pin → GPS geofence auto-detects arrival (200m) and jumps straight to POD → complete. `DestinationReachedScreen` (manual "confirm arrival" screen) removed; `LiveNavigationScreen` replaced (was a fake placeholder) and wired at `/trip/navigate` | ✅ (2026-07-28) |

### Fleet data onboarding (Excel templates + guide)
| Piece | State |
|---|---|
| `scripts/generate_excel_templates.py` — generates styled bulk-entry workbooks (banner, info cards, dropdown validation, sample rows) | ✅ |
| `MERCON_Drivers_Import_Template.xlsx` / `MERCON_Vehicles_Import_Template.xlsx` in `docs/templates/` + `frontend/public/templates/` (downloadable) | ✅ |
| Drivers sheet columns aligned to the real Prisma model + an `Assigned Vehicle Plate` column (dropped the speculative Email / Emergency-Contact columns — no schema fields for them) | ✅ (2026-08-04) |
| Vehicles sheet: ICCES device ID + `Assigned Driver Phone / Name` column | ✅ (2026-08-04) |
| `docs/MERCON_Fleet_Import_Guide.md` — column specs, validation rules, Prisma field mapping, owner instructions | ✅ |
| **Backend import endpoint (parse an uploaded workbook → create drivers/vehicles)** | ❌ **does not exist** — see §3 |

> ⚠️ Honest scope: these templates are a **manual data-collection format** the owner sends to the
> client. Nothing in the app ingests them yet — the filled workbook has to be entered by hand or
> imported by a future endpoint. The guide's "API Import Schema Mapping" section is a *spec for
> that future endpoint*, not a description of shipped code.

### Mobile backend endpoints (`/api/mobile/*`)
| Endpoint | State |
|---|---|
| `POST /mobile/login` (unified, returns role) | ✅ |
| `GET /mobile/trips/current` | ✅ |
| `POST /mobile/trips/:id/status` | ✅ |
| `POST /mobile/trips/:id/photo` | ✅ |
| `GET /mobile/trips/history` (past trips, `?limit`) | ✅ |
| `GET /mobile/notifications` + `POST /:id/read` (driver, keyed by `Notification.driverId`) | ✅ |
| Driver "Trip Assignment" notification on dispatch + driver-replace | ✅ delivers |
| `GET /mobile/profile` (identity, license, phone, active-trip vehicle) | ✅ |
| `POST /mobile/emergency` (alerts all active Admins + Operators) | ✅ |
| `GET /mobile/documents` (driver's own docs) + `GET /mobile/vehicle` (active-trip vehicle) | ✅ |

---

## 3. 🔜 What's next (remaining work)

Legend: ⬜ not started · 🔄 in progress · ✅ done

### Milestone 1 — Finish driver trip workflow
**Backend endpoints (missing):**
- ✅ `GET /mobile/trips/history` — driver's past trips
- ✅ `GET /mobile/notifications` (+ `POST /:id/read`) — driver notifications
- ✅ `POST /mobile/emergency` — emergency alert (notifies operators/admins)
- ✅ `GET /mobile/profile` — driver profile

**Wire driver screens (currently static UI):**
- ✅ `PickupVerificationScreen` → cargo photo + `AtPickup → InTransit` (`/trip/pickup`)
- ✅ `DeliveryVerificationScreen` → POD photo + `AtDelivery → Completed` (`/trip/delivery`); receiver-name/signature dropped (no schema field — owner decision)
- ✅ `LiveNavigationScreen` → real map + GPS geofence auto-detects `InTransit → AtDelivery` (expo-router `/trip/navigate`, replaces the old manual `DestinationReachedScreen`/`/trip/arrived`)
- ✅ `TripCompletedScreen` → real summary of the latest completed trip (`/trip/completed`)
- ✅ `TripsScreen` (history) — real Active/Upcoming/Completed tabs
- ✅ `NotificationsScreen` — real feed + mark read / mark all
- ✅ `ProfileScreen` — real identity/license/vehicle + working logout
- ✅ `DocumentsScreen` → `GET /mobile/documents` (real docs, expiry status, open file)
- ✅ `AssignedVehicleScreen` → `GET /mobile/vehicle` (active-trip vehicle + honest empty state)
- ✅ `EmergencyScreen` → `POST /mobile/emergency` (incident type + notes + GPS location now attached; reachable via SOS button on Home + Live Navigation — was previously unwired/unreachable); photo capture UI still local-only — backend has no attachment endpoint for emergency reports yet (needs a `DocType`/schema decision, flagged separately)
- ✅ `SettingsScreen` — real logout (toggles are local-only); reachable (`/settings`)
- ⬜ `ReplacementDriverScreen` / `SplashScreen` (as needed)

### Milestone 2 — Driver live GPS
- ✅ `expo-location` foreground tracking while a trip is active (~10s / 20m) — plugin added to `app.json`
- ✅ `socket.io-client` connect + emit `driver:location_update` (shared socket, backend receives it)
- ⬜ Handle background / locked screen / network drops (foreground done; background is a hardening step)
- 🔄 End-to-end: truck moves live on the operator's web map — code complete, needs real-device verification

**How it's wired:** `src/lib/socket.ts` (shared connection), `use-live-tracking.ts` (watch + emit),
`DriverLiveTracking.tsx` (headless, polls current trip) rendered on the driver landing. Streams
`{ tripId, driverId, lat, lng, speed }`; the web `TripTrackingPage` already listens on
`trip:location_update:<tripId>`.

### Milestone 3 — Operator mobile screens
- ✅ `_layout.tsx` shows `OperatorBottomNav` for both `Operator` and `Admin` roles (was Operator-only, so Admin got the driver nav — fixed)
- ✅ `src/app/operator/{trips,trip-details,create-trip,drivers,vehicles,invoices}.tsx` route files created; registered in the root `Stack` and `TAB_ROUTES`
- ✅ `OperatorBottomNav` — Trips/Drivers tabs and the FAB now navigate to real routes (previously Drivers→`/documents`, Trips→driver `/trips`, FAB did nothing)
- ✅ `HomeScreen` (dashboard metrics) — real KPIs via `/reports/summary` + active trips via `/trips`
- ✅ `TripListScreen` — real `/trips` with status filters, KPI chips, search; cards tap through to `TripDetailsScreen`
- ✅ `TripDetailsScreen` — real trip via `GET /trips/:id` (timeline built from status + stop timestamps, cargo, driver, vehicle); "Call Driver" opens the dialer; **real lifecycle actions** now replace the old "coming soon" stub: contextual next-step button per status (`POST /trips/:id/pickup/arrive` → `PATCH /trips/:id/status` InTransit/AtDelivery/Completed), "Replace Driver" (live available-drivers picker modal → `POST /trips/:id/replace-driver`), "Cancel Trip" (`PATCH .../status` Cancelled); "Track Live" still shows a "coming soon" alert (no map yet)
- ✅ `CreateTripScreen` — real customers (`GET /customers`) + available drivers/vehicles (`GET /drivers|vehicles?status=Available`); posts `POST /trips` with pickup/dropoff lat-lng (plain numeric inputs, no map picker yet); form fields now use the shared `Input`/`Card` components instead of raw `TextInput`
- ✅ `DriverListScreen` — real `/drivers` (status filters, search, tap-to-call); tapping a card now opens `DriverEditScreen` (`PATCH /drivers/:id` — name/phone/license/status)
- ✅ `VehicleListScreen` — real `/vehicles` (status filters, stats, search); tapping a card now opens `VehicleEditScreen` (`PATCH /vehicles/:id` — plate/capacity/asset type/status)
- ✅ `VehicleRenewalScreen` — real vehicle documents via `GET /documents?entity_type=Vehicle` joined with `GET /vehicles` for plate numbers; due/critical/overdue buckets derived from `expiry_date` (no fake doc types/costs — uses the real `DocType`/`DocStatus` enums); reachable from the Home KPI "documents expiring soon" alert and from the new "More" hub; "Renew Now" still shows a "coming soon" alert (no re-upload flow yet)
- ✅ `InvoiceListScreen` — real `/invoices` (status filters, stat cards, search); Pending/Overdue invoices now show a "Mark as Paid" action (`PATCH /invoices/:id/status`); fixed a real bug where `Paid`/`Draft`/`Overdue` were missing from the status-color map and silently rendered as gray "Pending"
- ✅ `CustomerListScreen` + `CustomerEditScreen` (new) — full customer list/search/active-filter via `GET /customers`, create via `POST /customers`, edit (incl. active/inactive toggle) via `PATCH /customers/:id`; reachable from the new "More" hub and its own "+" button
- ✅ `MoreScreen` (new, `/operator/more`) — fixes a real navigation gap: `OperatorBottomNav`'s "More" tab used to route straight to the **driver's** settings screen, meaning Vehicles/Invoices/Vehicle Renewals (and now Customers) had no in-app entry point at all, only reachable via a raw deep link. The "More" tab now opens this hub (Fleet/Invoices/Customers/Vehicle Renewals + sign out) first.
- ✅ Fixed a duplicate-bottom-nav bug: `OperatorBottomNav` is already rendered globally as a floating overlay in `_layout.tsx`; an earlier pass had also rendered it inside 5 individual screens, showing two nav bars stacked.
- ✅ UI-kit consistency pass across all 8 operator screens: swapped hand-rolled filter pills/cards/buttons for the shared `FilterChip`/`Card`/`Button`/`StatusBadge` components, replaced hardcoded hex colors with `theme/tokens.ts` values (several were off-palette drift, e.g. `#D97706`, `#FFF7ED`, `#1A1A1A` for the dark header).

### Milestone 3.5 — Fleet bulk import (owner onboarding)
- ✅ Styled Excel templates + import guide (drivers & vehicles, incl. assignment columns)
- ✅ Excel export from the web Drivers/Vehicles list pages (round-trips the same columns)
- ⬜ `POST /drivers/import` / `POST /vehicles/import` — parse the uploaded workbook (`xlsx`/`exceljs`),
  validate with Zod, upsert on the unique keys (driver phone/license, vehicle plate), resolve the
  assignment columns, and report per-row errors. Field mapping already specced in the guide.
- ⬜ Web UI: "Import from Excel" on the Drivers/Vehicles list pages (upload → preview → confirm)

### Milestone 3.5 — Delay reporting follow-ups
- ⬜ Push notifications so a delay alert reaches a phone that is locked / app closed (currently in-dashboard only)
- ⬜ Geofence/ICCES departure time as an independent second source, to match the client's three-way cross-check (blocked on credentials)
- ⬜ Optional: auto-flag dwell time past ~5h as chargeable (client rarely bills the first 1–2h, so this stays a manual operator decision for now)
- ⬜ Optional: reason capture on the operator mobile app (web-only today)

### Milestone 4 — Testing, builds, handover
- ⬜ Real-phone test, both roles (Android + iPhone)
- 🔄 EAS builds — APK (Android) + TestFlight (iOS); app linked to an EAS project (`c99aab6`), no build run yet
- ⬜ Database backup set up + tested once
- ⬜ Short user guide (operator + driver, with screenshots)
- ⬜ Full end-to-end acceptance: create trip → driver runs it → invoice appears

### Schema note — driver notifications (resolved 2026-07-25, Option A)
`Notification` now has a nullable `userId` **or** `driverId` recipient (added `driverId`,
made `userId` optional). Web notifications still key off `userId`; driver notifications
key off `driverId`. `createDriverNotification()` + the trip-assignment trigger use it.
**Schema change deploys via `prisma db push --accept-data-loss` — additive/widening, no data loss.**

### Deferred (not v1)
- Push notifications (FCM) · map upgrade (Google/Mapbox) · OTP SMS login · big automated test suite · ICCES live creds (env vars pending)

---

## 4. Screen wiring tracker (mobile)

| Screen | Role | Wired? |
|---|---|---|
| LoginScreen | shared | ✅ |
| HomeScreen (trip flow + photos) | driver | ✅ |
| TripsScreen (history + active/upcoming tabs) | driver | ✅ |
| NotificationsScreen (feed + mark read/all) | driver | ✅ |
| ProfileScreen (identity/license/vehicle + logout) | driver | ✅ |
| EmergencyScreen (alert → operators/admins) | driver | ✅ |
| LiveNavigationScreen (live map, GPS auto-arrival → AtDelivery) | driver | ✅ |
| PickupVerificationScreen (cargo photo → InTransit) | driver | ✅ |
| DeliveryVerificationScreen (POD photo → Completed) | driver | ✅ |
| TripCompletedScreen (completion summary) | driver | ✅ |
| SettingsScreen (logout) | driver | ✅ |
| DocumentsScreen (real docs + expiry) | driver | ✅ |
| AssignedVehicleScreen (active-trip vehicle) | driver | ✅ |
| ReplacementDriver/Splash | driver | ⬜ static (secondary) |
| HomeScreen (`features/dashboard`: header/context/search, 2 metric cards, Active Vehicles carousel, Document Expiry section — NativeWind + React Query) | operator | ✅ (2026-08-05) |
| TripListScreen (filters + KPI chips + search, tap→details) | operator | ✅ |
| TripDetailsScreen (real trip, timeline, call driver, lifecycle actions, replace driver, cancel) | operator | ✅ |
| CreateTripScreen (real customers/drivers/vehicles, POST /trips) | operator | ✅ |
| DriverListScreen (`features/drivers`: 2 KPI tiles, search/filter/sort, infinite scroll, tap→details) | operator | ✅ (2026-08-05) |
| DriverDetailsScreen (profile, assigned vehicle, contact, documents, current assignment, performance, call/message) | operator | ✅ (2026-08-05) |
| DriverEditScreen (PATCH /drivers/:id) | operator | ✅ |
| VehicleListScreen (filters + stats + search, tap→edit) | operator | ✅ |
| VehicleEditScreen (PATCH /vehicles/:id) | operator | ✅ |
| InvoiceListScreen (filters + stats + search, mark-as-paid) | operator | ✅ |
| VehicleRenewalScreen (real doc expiry tracker, reachable from Home alert + More hub) | operator | ✅ |
| CustomersScreen (`features/customers`: KPI rail, search/filter/sort, infinite scroll, per-customer trips/revenue/rate card, overflow menu with role-gated suspend/delete, Create Trip) | operator | ✅ (2026-08-05, rebuilt) |
| CustomerEditScreen (create + edit, PATCH/POST /customers) | operator | ✅ |
| MoreScreen (Fleet/Invoices/Customers/Renewals hub + sign out) | operator | ✅ |

**Wired: 28 / 31 screens** (all core driver screens + all operator screens except the secondary
driver Replacement/Splash screens). Operator nav now actually reaches every wired operator screen —
Admin included — including the ones previously stranded behind the driver settings "More" route.

**Driver navigation now works** (expo-router): the bottom nav (Home/Trips/Profile) and Profile's
quick actions + Notifications link actually navigate — so the already-wired Trips, Notifications,
and Profile screens are reachable in the running app for the first time. Routes live at
`src/app/{trips,profile,notifications,documents,vehicle,settings}.tsx`.

**Driver trip flow — fully wired end to end, straight-through** via expo-router (`src/app/trip/*`):
Dispatched →(inline)→ AtPickup →`/trip/pickup` (cargo photo)→ InTransit →`/trip/navigate`
(live map, GPS auto-detects arrival within 200m, manual "I've Arrived" fallback)→
AtDelivery →`/trip/delivery` (POD photo)→ Completed →`/trip/completed` (summary). No more
detour back to Home between pickup and delivery. Home still routes into each step by status
and refetches on focus (for a driver who backgrounds the app mid-flow).

---

## 5. Verification & ops status
- Backend `tsc`: clean · Web `tsc --noEmit`: clean · Mobile `tsc --noEmit`: 0 errors (as of last session).
- Trip creation (driver required, auto-dispatch, availability conflict, driver notification) verified end-to-end against a local Postgres + running API (manual curl pass, test rows cleaned up).
- Web location picker (Nominatim address search + Leaflet pin drop/drag, recenter-on-search) verified in-browser.
- `react-native-maps` added (mobile) for the new live-map screen; not yet run in a simulator/device — see below.
- ❌ **Not yet run on a real phone against the live server** — this is the next real check.
- Git identity reminder: ensure commits use `sayedhysampm@gmail.com`.

---

## 6. Full-stack audit remediation (2026-07-29)

A full audit (backend/web/mobile/deploy) found 6 critical, ~13 high, ~10 medium, and
several low-severity issues. Fixing in phases per `~/.claude/plans/hidden-painting-deer.md`
(local plan file, not in repo). Status:

- ✅ **Phase 0 — Credential rotation (code)**: `docker-compose.yml` now requires
  `POSTGRES_USER`/`POSTGRES_PASSWORD` as GitHub secrets (was hardcoded `mercon_user`/
  `mercon_password`), Postgres port bound to `127.0.0.1` only (was public on `15432`),
  `ci-cd.yml` passes the new secrets through with the same abort-if-unset guard as
  `JWT_SECRET`. **Owner action still needed**: generate a real password, add
  `POSTGRES_USER`/`POSTGRES_PASSWORD`/`SEED_ADMIN_PASSWORD` as GitHub Actions secrets
  before the next deploy, or the container will fail to start.
- ✅ **Phase 1 — Critical, item 1**: `prisma/seed.ts` rewritten to seed only the two
  canonical accounts (`admin`, `operator`) per this file's own rules — no more fake
  customers/drivers/vehicles/trips/invoices seeded into production on every deploy.
  **Not done yet**: already-seeded fake rows already in the production DB are untouched;
  owner needs to review and manually clean those up.
- ✅ **Phase 1, item 2**: `POST/PUT /users` now Zod-validates `role` to `Admin|Operator`
  only — previously any string was accepted, so an Admin could set `role: "Driver"`
  through User Management, contradicting the "Driver users must not be creatable there"
  rule.
- ✅ **Phase 1, item 3**: Socket.IO now requires a valid JWT in the connection handshake
  (was fully open — anyone could connect and listen to every live GPS/notification
  event). Sockets auto-join a private room by identity; trip GPS relay validated against
  the sending driver's own assigned trip and scoped to a `trip:<id>` room; dashboards/
  drivers must `join:trip` (authorized server-side) to receive it.
- ✅ **Phase 1, item 4**: Driver `EmergencyScreen` was fully built but unreachable (no
  route, no nav entry) and used a stale `navigation` prop that would have silently no-op'd
  even if reachable. Fixed: converted to `expo-router`'s `useRouter`, added a
  `/trip/emergency` route, added an SOS button on the driver Home screen header and on
  `LiveNavigationScreen`'s top bar, and `send()` now attaches the device's current GPS
  coordinates.
- ✅ **Follow-up (owner-approved)**: `TripTrackingPage.tsx` (web) was found to no longer
  use a real socket connection — it rendered simulated telemetry
  (`useSimulatedTelemetry`/`PREDEFINED_ROUTES`) instead of live GPS, with fabricated
  "Riyadh Dry Port"/"Jeddah Islamic Port" location names and a fake ETA/progress bar on
  every trip regardless of actual route. Rewired to the real authenticated Socket.IO
  connection (`join:trip`, listens on `trip:location_update:<id>`), shows real pickup/
  dropoff coordinates instead of hardcoded port names, and a real "LIVE"/"DISCONNECTED"
  status + "last update" timestamp instead of the always-green fake indicator. Verified
  end-to-end locally (simulated a driver GPS emit over an authenticated socket, confirmed
  the truck marker/speed/timestamp updated on the dashboard in real time).
- ✅ **Follow-up (owner-approved)**: Emergency incident photos now actually reach the
  backend — added `DocType.Emergency` to `schema.prisma` (additive enum value, pushed
  locally via `prisma db push`, will auto-apply on next production deploy per this repo's
  existing `prisma db push --accept-data-loss` deploy step), added multipart upload
  (`upload.array('photos', 4)`) to `POST /mobile/emergency`, and the endpoint now creates
  a `Document` per photo linked to the driver's active trip. Verified end-to-end via curl
  (uploaded a real file, confirmed the `Document` row was created with the right
  `entity_id`/`doc_type`).
- ✅ **Phase 2 (High) — items 11–17 (session continued)**:
  - **Item 11** (mobile global 401 handling): `api.ts` response interceptor now clears
    SecureStore + routes to `/login` on any 401 — done in previous session.
  - **Item 12** (duplicate photo upload on retry): `PickupVerificationScreen` and
    `DeliveryVerificationScreen` now track uploaded-photo indices in a `useRef<Set<number>>`;
    a retry only re-uploads photos that failed, not those already successfully sent. Also
    added a `inFlight` ref to prevent double-tap re-entrancy (React state updates are async,
    so a ref guard is needed in addition to the `submitting` state). Also fixed
    `camera.ts` which had been accidentally doubled (all functions declared twice) — removed
    the stale second copy; the first copy (with `expo-image-manipulator` resize to 1280px)
    is the correct one.
  - **Item 13** (web 401 vs 403 split): `src/lib/api.ts` now only force-clears the session
    on 401 (expired/revoked token). A 403 (authorised user, wrong role) is now rejected
    as a normal error so the calling page can show an inline "You don't have permission"
    message instead of silently logging the operator out.
  - **Item 14** (block expired-license driver onboarding): `AddDriverPage.tsx` now includes
    `isExpiryValid` in `isFormValid` and in `handleSubmit`, blocking onboarding when the
    license is already expired. Same check added to `CreateDriverModal.tsx` (the inline
    "Add Driver" modal on Create Trip page).
  - **Item 15** (cargo type field): *(superseded 2026-08-07 — the cargo type dropdown
    described below was never actually wired in; `CreateTripPage.tsx` still submits a
    hardcoded `'General Goods'`, and the hazmat badge/flag mentioned here was removed
    project-wide, see top of file)*
  - **Item 16** (time ordering check): `CreateTripPage.tsx` now validates
    `dropoffTime > pickupTime` before submission and shows a clear error with the form
    switching back to the Route tab.
  - **Item 17** (invoice subtotal from rate card): `CreateInvoicePage.tsx` now fetches the
    selected customer's active rate card on trip selection and auto-fills the subtotal from
    `base_price`. The field stays editable; an "Auto-filled from rate card — editable" badge
    appears and the input gets a green border when auto-filled.
- ✅ **Phase 3 (Medium) — completed (session continued)**:
  - **Item 20** (sendBulkCommunication): UI updated to clearly state "Not connected to SMS provider" to avoid user confusion.
  - **Item 21** (Reports pagination): Modified `reportsController`, `reportsService`, `FleetPerformancePage`, and `DriverPerformancePage` to handle pagination properly and extract data array.
  - **Item 22** (isError handling/banners): Systematically updated `DataTable.tsx` references across all major list pages (Drivers, Vehicles, Trips, Invoices, Rate Cards, Customers, User Management) and `DashboardPage` to handle errors correctly.
  - **Item 23** (Sidebar notification badge): Wired `Sidebar.tsx` to use react-query and `notificationService` to display real unread notification counts instead of a hardcoded value.
  - **Item 24** (Trip-status transition guard): Implemented transition guard in `TripListPage.tsx` to prevent selecting invalid statuses for a trip, mirroring the backend validation. (`TripDetailsPage.tsx` was verified to already be safe).
  - **Item 25** (Attach JWT to Socket.IO in TripTracking): Verified `TripTrackingPage.tsx` already attaches JWT to `auth.token` and has a live status indicator.
  - **Item 26** (CI/CD health-check for docker): Added `pg_isready` healthcheck to `postgres-db` and `curl` healthcheck to `mercon-api` in `docker-compose.yml`.
  - **Items 27 & 28** (TLS/HSTS and tighten CORS): Installed `helmet`, configured HSTS, and restricted CORS to specific dashboard origins in `backend/api-server/src/index.ts`.
- ✅ **Phase 4 (Low/Cleanup) — completed (session continued)**:
  - **Item 29** (Add Zod to createMaintenanceRecord): Added Zod schema validation to `maintenanceController.ts`.
  - **Item 30** (Consolidate multer configs): Removed duplicate `multer` config from `uploadController.ts` and reused the one in `middlewares/upload.ts`.
  - **Item 31** (Add index on Trip): Added `@@index([vehicleId, driverId])` to the `Trip` model in `schema.prisma`.
  - **Item 32** (Dead code removal): Confirmed unused routes (like trackingRoutes) are deleted.
  - **Item 33** (Replace implicit any): Replaced `any` with `Prisma.TripWhereInput` in `tripController.ts`.
  - **Item 34** (Improve mobile NavigationCard UI padding): Improved bottom padding on the `LiveNavigationScreen` to handle safe area constraints gracefully.
  - **Item 35** (Standardize error response shape): Refactored `uploadController.ts` to follow the standard `error: { code: '...', message: '...' }` pattern.

---

## Update protocol

**This file is the project's status memory. Update it in the SAME change that alters reality:**

1. **When code/schema/endpoint/screen changes** — flip the matching ⬜/🔄/✅, move rows
   between §2 (Completed) and §3 (Next), and update the §1 TL;DR percentages if an area
   crossed a threshold.
2. **When a step is finished** — mark it ✅ and add the commit hash where useful.
3. **Always bump `Last updated`** at the top to today's date.
4. Keep it honest — verify against code, never mark ✅ from intent alone.

Detailed session narratives go in `docs/progress/<date>.md`. The forward-looking plan
and locked decisions live in `PLAN.md`. **This file = current state at a glance.**
