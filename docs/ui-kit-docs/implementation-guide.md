# MERCON Implementation Guide

## 12-Phase Build Order

Build the platform in this exact sequence. Do not begin a phase until all deliverables in the previous phase are complete and reviewed.

---

## Phase 1 — Design Tokens

**Goal:** Establish the single source of truth for all design values. Nothing else can be built without this.

**Deliverables:**

- [ ] `react-native/theme/tokens.ts` — Complete implementation including:
  - `Colors` object (all 30+ color values)
  - `Spacing` object (10 values, xs through 5xl)
  - `Radius` object (8 values, xs through full)
  - `Typography` object (15 type styles)
  - `Shadows` object (5 shadow levels)
  - `TripStatus` type
  - `VehicleStatus` type
  - `DocStatus` type
  - `getStatusColors(status: string)` function
- [ ] `web/styles/tokens.css` — CSS custom properties derived from the same values
- [ ] Unit tests: verify `getStatusColors` returns correct pairs for all 12 status strings, returns fallback for unknown status

**Verification:**
- Import `Colors.primary` in a test file and confirm it equals `#E8450F`
- Import `getStatusColors('Completed')` and confirm `{ color: '#16A34A', bg: '#F0FDF4' }`
- Import `getStatusColors('unknown')` and confirm fallback `{ color: '#6E6E80', bg: '#F5F5F7' }`

---

## Phase 2 — Foundation Layer

**Goal:** Set up navigation infrastructure, font loading, and screen scaffolding.

**Deliverables:**

- [ ] Font loading: Plus Jakarta Sans Regular, Medium, SemiBold, Bold, ExtraBold loaded at app launch
- [ ] `react-navigation` stack navigators configured for Driver and Operator flows
- [ ] SafeAreaProvider and NavigationContainer wrapping App root
- [ ] StatusBar configuration per screen (light-content on dark headers, dark-content on light headers)
- [ ] Base screen template: SafeAreaView + ScrollView or FlatList shell with correct background color
- [ ] Global error boundary component
- [ ] `AuthContext` with signIn / signOut / token storage

**Verification:**
- App launches without font FOUT (flash of unstyled text)
- Navigation stack renders without errors in blank state

---

## Phase 3 — Atom Components

**Goal:** Build the smallest, most-reused components from which everything else is composed.

**Deliverables:**

- [ ] `Typography.tsx`: Heading, Title, Body, Caption, Overline, Mono — all 6 helpers with all 8 color options
- [ ] `Badge.tsx`: Badge, StatusBadge, SolidBadge, FilterChip — all 4 variants
- [ ] `Avatar.tsx`: Avatar (all 4 sizes, all 3 online states), AvatarGroup (with overflow)
- [ ] `components/index.ts` barrel export

**Storybook stories for each:**
- Typography: all 6 components × all 8 color options
- Badge: StatusBadge with all 12 status strings, FilterChip active/inactive
- Avatar: all 4 sizes × online/busy/offline × with/without dot, AvatarGroup with 3, 5, 7 items

**Verification:**
- Every StatusBadge displays with the correct color pair for each status
- AvatarGroup shows overflow correctly at max=3, max=5
- All Typography components use Plus Jakarta Sans

---

## Phase 4 — Molecule Components

**Goal:** Build interactive input and container components.

**Deliverables:**

- [ ] `Input.tsx`: Input component with all 5 states (default, focused, error, success, disabled), label, iconLeft, iconRight, errorText, successText, multiline variant
- [ ] `Input.tsx`: SearchInput component
- [ ] `Card.tsx`: Card (default and dark variants, elevated prop), DarkCard
- [ ] `Button.tsx`: Button with all 6 variants × 3 sizes × disabled state × loading state × iconLeft + iconRight

**Verification:**
- Input focus ring appears and is orange at 25% opacity
- Input error state shows red background and error text
- Button loading state shows spinner and disables onPress
- Button primary variant has orange glow shadow
- Card dark variant is `#1C1C2E`, default variant is `#FFFFFF`

---

## Phase 5 — Organism Components (Navigation)

**Goal:** Build the bottom navigation components.

**Deliverables:**

- [ ] `DriverBottomNav.tsx`: dark pill, 3 tabs (Home/Trips/Profile), lucide icons, orange active state
- [ ] `OperatorBottomNav.tsx`: dark pill, 4 tabs + center FAB, lucide icons, FAB is white circle with orange border
- [ ] Both navs integrated with React Navigation tab navigator
- [ ] Active tab state synchronized with navigator's current route

**Verification:**
- Active tab shows orange icon and label
- Inactive tabs show `rgba(255,255,255,0.45)` icon and label
- FAB press triggers `onFabPress` callback
- Nav pill has correct shadow (Shadows.nav)
- Switching tabs updates the active state correctly

---

## Phase 6 — Templates (Screen Layouts)

**Goal:** Build the reusable screen layout templates before filling in specific screen content.

**Deliverables:**

- [ ] `DriverScreenTemplate`: SafeAreaView + optional dark header + ScrollView/FlatList + DriverBottomNav
- [ ] `OperatorScreenTemplate`: SafeAreaView + optional dark header + ScrollView/FlatList + OperatorBottomNav
- [ ] `ListScreenTemplate`: Header + SearchInput + FilterChip row + FlatList + BottomNav
- [ ] `DetailScreenTemplate`: Dark header card + ScrollView content + floating action buttons
- [ ] `FormScreenTemplate`: Header + ScrollView form + sticky submit button
- [ ] `WebDashboardLayout`: Fixed sidebar + scrollable main content area

**Verification:**
- Template renders on iPhone SE without overflow
- Template renders on iPhone 14 Pro Max without excessive whitespace
- Keyboard does not cover the focused input (use KeyboardAvoidingView)

---

## Phase 7 — Driver App Screens (16 screens)

**Goal:** Build all 16 Driver App screens in dependency order.

**Build order:**
1. SplashScreen (no dependencies)
2. LoginScreen (Input, Button)
3. OTP Verification (Input, Button)
4. HomeScreen — Driver (DarkCard, Card, StatusBadge, Button, DriverBottomNav)
5. TripsScreen (SearchInput, FilterChip, StatusBadge, DriverBottomNav)
6. TripDetails — Driver (Card, DarkCard, StatusBadge, Avatar)
7. ProfileScreen (Avatar, Card, Button, Mono, DriverBottomNav)
8. NotificationsScreen (Card)
9. SettingsScreen (Card)
10. DocumentsScreen (Card, StatusBadge, Button)
11. AssignedVehicleScreen (Card, DarkCard, StatusBadge)
12. ActiveTripScreen (DarkCard, Card, StatusBadge, Button, DriverBottomNav)
13. LiveNavigationScreen (full-screen map)
14. PickupVerificationScreen (Input, Button, Card)
15. DeliveryVerificationScreen (Input, Button, Card)
16. TripCompletedScreen (Button, animations)
17. EmergencyScreen (Button)
18. ReplacementDriverScreen (Input, Button)
19. DestinationReachedScreen (Card, Button)
20. EarningsScreen (DarkCard, FilterChip)

**Deliverables per screen:**
- [ ] Component renders without errors in all states
- [ ] All interactive elements trigger correct navigation
- [ ] Loading state shows skeleton or spinner
- [ ] Empty state shows appropriate message/illustration
- [ ] Error state shows error message
- [ ] All statusBar styles applied correctly

---

## Phase 8 — Operator App Screens (41 screens)

**Goal:** Build all Operator App screens. Reuse shared components; only build operator-specific additions.

**Build order:**
1. HomeScreen — Operator (DarkCard, Card, StatusBadge, Avatar, OperatorBottomNav)
2. TripListScreen (SearchInput, FilterChip, StatusBadge, Mono, OperatorBottomNav)
3. TripDetailsScreen (DarkCard, Card, StatusBadge, Avatar, Button)
4. CreateTripScreen (Input, Button, Card, OperatorBottomNav FAB trigger)
5. DriverListScreen (SearchInput, FilterChip, Avatar, StatusBadge, Mono)
6. DriverDetailsScreen (DarkCard, Card, Avatar, StatusBadge, Button)
7. AddDriverScreen (Input, Button, Card)
8. VehicleListScreen (SearchInput, FilterChip, StatusBadge, Mono)
9. VehicleDetailsScreen (DarkCard, Card, StatusBadge, Mono)
10. VehicleRenewalScreen (Card, StatusBadge, Mono, Button)
11. InvoiceListScreen (SearchInput, FilterChip, StatusBadge, Mono)
12. InvoiceDetailsScreen (Card, StatusBadge, Mono, Button)
13. CreateInvoiceScreen (Input, Button, Card)
14. CustomerListScreen (SearchInput, Avatar, Card)
15. CustomerDetailsScreen (DarkCard, Card, Avatar, Button)
16. RateCardListScreen (Card, Badge)
17. CreateRateCardScreen (Input, Button, Card)
18. NotificationsScreen — Operator (Card)
19. ProfileScreen — Operator (Avatar, Card, Button)
20. SettingsScreen — Operator (Card)
21–41. Remaining screens following the same component patterns

---

## Phase 9 — Web Dashboard (44 screens)

**Goal:** Build the web enterprise dashboard.

**Build order:**
1. DashboardLayout (sidebar + main area)
2. SidebarNav component
3. Overview / Home Dashboard (KPI cards, active trips table, alerts)
4. Trip List (table with sorting/filtering/pagination)
5. Trip Details (detail view with timeline)
6. Create Trip (multi-step form)
7. Driver List (table)
8. Driver Details
9. Add Driver
10. Vehicle List (table)
11. Vehicle Details
12. Vehicle Renewals (alert-focused list)
13. Customer List (table)
14. Customer Details
15. Invoice List (table with financial data)
16. Invoice Details
17. Create Invoice
18. Rate Card List
19. Create Rate Card
20–23. Reports pages (Revenue, Performance, Driver, Vehicle)
24–27. Settings pages (General, Users, Billing, Integrations)
28. Notifications
29. Profile

---

## Phase 10 — Flows and Animations

**Goal:** Apply motion and animation to all interactive transitions.

**Deliverables:**
- [ ] Page transition animations (push = slide right, modal = slide up)
- [ ] Input focus ring animation (200ms ease-out)
- [ ] Button press scale animation (150ms ease-out, scale 0.96)
- [ ] Progress bar fill animation on mount (600ms ease-out)
- [ ] Skeleton shimmer on all loading states
- [ ] FilterChip toggle animation (150ms ease-out color transition)
- [ ] TripCompleted success animation (spring entry)
- [ ] Status dot pulse animation
- [ ] Reduced motion compliance for all animations above

---

## Phase 11 — Accessibility Audit

**Goal:** Verify WCAG 2.1 AA compliance across all screens.

**Deliverables:**
- [ ] All interactive elements have `accessibilityRole` set
- [ ] All buttons have `accessibilityLabel` matching visible label
- [ ] All inputs have `accessibilityLabel` and `accessibilityHint`
- [ ] Status badges announce status via `accessibilityLabel`
- [ ] Focus order verified (web)
- [ ] Focus indicators visible (web)
- [ ] Keyboard navigation complete (web)
- [ ] VoiceOver testing passed on iOS (all 16 driver screens, 5 core operator screens)
- [ ] TalkBack testing passed on Android (same screens)
- [ ] Touch targets ≥44pt verified on all primary interactions
- [ ] Reduced motion respected
- [ ] Contrast ratios verified using automated tool (axe, Colour Contrast Analyser)

---

## Phase 12 — QA and Optimization

**Goal:** Production readiness — performance, visual polish, cross-device consistency.

**Deliverables:**
- [ ] Design checklist completed for every screen (see `design-checklist.md`)
- [ ] FlatList performance: all lists use `getItemLayout`, `removeClippedSubviews`, `React.memo` items
- [ ] Image loading: all images use fast-image or equivalent with placeholder
- [ ] Bundle size audit: no unused icons imported
- [ ] Memory leak audit: all `useEffect` cleanup functions present
- [ ] Error boundary tested (force errors on key screens)
- [ ] Deep link testing (if implemented)
- [ ] Offline mode tested (airplane mode)
- [ ] RTL layout check (Arabic UI)
- [ ] Sign-off testing on: iPhone SE, iPhone 14, iPhone 14 Pro Max, Pixel 5, Galaxy S23

---

## Milestone Schedule Reference

| Milestone | Phases | Estimated Output |
|-----------|--------|-----------------|
| M1 — Foundation | 1–2 | Tokens + navigation skeleton |
| M2 — Components | 3–5 | Complete component library |
| M3 — Driver App | 6–7 | 16 driver screens functional |
| M4 — Operator App | 8 | 41 operator screens functional |
| M5 — Web Dashboard | 9 | 44 web screens functional |
| M6 — Polish | 10–12 | Animations, accessibility, QA |
