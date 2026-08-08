# MERCON System Architecture

## Component Hierarchy

```
Design Tokens (tokens.ts)
│
├── Atom Layer
│   ├── Typography (Heading, Title, Body, Caption, Overline, Mono)
│   ├── Badge (Badge, StatusBadge, SolidBadge, FilterChip)
│   └── Avatar (Avatar, AvatarGroup)
│
├── Molecule Layer
│   ├── Input (Input, SearchInput)
│   ├── Button
│   └── Card (Card, DarkCard)
│
├── Organism Layer
│   ├── DriverBottomNav
│   ├── OperatorBottomNav
│   ├── TripCard (composed from Card + StatusBadge + Typography + Avatar)
│   ├── DriverCard (composed from Card + Avatar + StatusBadge + Button)
│   └── VehicleCard (composed from Card + StatusBadge + Badge)
│
├── Template Layer
│   ├── DriverScreenTemplate (SafeAreaView + ScrollView + DriverBottomNav)
│   ├── OperatorScreenTemplate (SafeAreaView + ScrollView + OperatorBottomNav)
│   ├── ListScreenTemplate (Header + SearchInput + FilterChips + FlatList + Nav)
│   ├── DetailScreenTemplate (DarkHeader + ScrollView content)
│   └── FormScreenTemplate (Header + ScrollView form + Submit)
│
└── Screen Layer
    ├── Driver screens (16)
    ├── Operator screens (41)
    └── Web screens (44)
```

---

## Dependency Graph

```
tokens.ts
  └── colors, spacing, radius, typography, shadows, status helpers

Typography.tsx
  ← tokens.ts (Typography, Colors)

Badge.tsx
  ← tokens.ts (Colors, Spacing, Radius, Typography, getStatusColors)

Avatar.tsx
  ← tokens.ts (Colors, Radius, Typography)

Input.tsx
  ← tokens.ts (Colors, Spacing, Radius, Typography)

Card.tsx
  ← tokens.ts (Colors, Radius, Shadows)

Button.tsx
  ← tokens.ts (Colors, Spacing, Radius, Typography, Shadows)

DriverBottomNav.tsx
  ← tokens.ts (Colors, Spacing, Radius, Shadows)

OperatorBottomNav.tsx
  ← tokens.ts (Colors, Spacing, Radius, Shadows)

components/index.ts
  ← Button, Badge, Card, Input, Avatar, Typography (all)

screens/driver/*
  ← components/index.ts
  ← navigation/DriverBottomNav.tsx
  ← theme/tokens.ts (for screen-level styles not covered by components)

screens/operator/*
  ← components/index.ts
  ← navigation/OperatorBottomNav.tsx
  ← theme/tokens.ts

react-native/index.ts (root barrel)
  ← theme/tokens.ts
  ← components/index.ts
  ← navigation/DriverBottomNav.tsx
  ← navigation/OperatorBottomNav.tsx
```

**Circular dependency rule:** tokens.ts must never import from any component. Components must never import from screens.

---

## Shared Components

These components are used across both Driver and Operator apps, and their web equivalents:

| Component | Driver App | Operator App | Web Dashboard |
|-----------|-----------|-------------|---------------|
| StatusBadge | Trip status, document status | All statuses | All statuses |
| FilterChip | Trip filter | Trips, drivers, vehicles filter | Table filters |
| Card | Content containers | Content containers | Content panels |
| DarkCard | Dashboard stats | Dashboard stats | KPI cards |
| Button | Auth, trip actions | All forms, actions | All forms, actions |
| Input | Auth, forms | All forms | All forms |
| SearchInput | Trips list | All list screens | Table search |
| Avatar | Driver profile | Driver cards | Driver columns |
| AvatarGroup | — | Multiple drivers | Assignment panels |
| Typography helpers | All text | All text | All text (web-adapted) |

---

## Design Token Architecture

```
tokens.ts exports:
│
├── Colors: Record<string, string>
│   ├── Primary group (primary, primaryLight, primaryDark)
│   ├── Neutral group (black, dark, darkCard, gray50-gray900, white)
│   ├── Semantic group (success, warning, danger, info, purple, with Light variants)
│   ├── Navigation group (navBg)
│   └── Status chip group (statusCompleted, statusCompletedBg, etc.)
│
├── Spacing: Record<string, number>
│   └── xs(4) sm(8) md(12) base(16) lg(20) xl(24) 2xl(32) 3xl(40) 4xl(48) 5xl(64)
│
├── Radius: Record<string, number>
│   └── xs(4) sm(8) md(12) lg(16) xl(20) 2xl(24) 3xl(32) full(9999)
│
├── Typography: Record<string, TextStyle>
│   ├── Display (displayLarge, displayMedium, displaySmall)
│   ├── Heading (headingXL, headingL, headingM, headingS)
│   ├── Body (bodyLarge, bodyMedium, bodySmall)
│   ├── Label (caption, overline)
│   ├── Button (buttonLarge, buttonMedium, buttonSmall)
│   └── Mono
│
├── Shadows: Record<string, ShadowStyle>
│   └── sm md lg primary nav
│
├── Types: TripStatus | VehicleStatus | DocStatus
│
└── getStatusColors(status: string): { color: string; bg: string }
```

---

## Theme Architecture

The current system is a single light theme. The architecture is prepared for dark mode:

### Current state
- All colors hardcoded as hex values in `tokens.ts`
- Light mode only

### Dark mode preparation
The token structure should be evolved to:

```typescript
// Future structure (not yet implemented)
const light = { background: '#F5F5F7', surface: '#FFFFFF', ... };
const dark = { background: '#111111', surface: '#1A1A1A', ... };

// Use ColorScheme from react-native to select
const theme = useColorScheme() === 'dark' ? dark : light;
```

Current dark elements (`#1C1C2E` navigation, dark cards) are intentional in the light theme — they are not dark mode UI, they are the dark accent surface within the light design.

---

## Navigation Architecture (React Navigation)

### Driver App Navigation Structure

```
RootNavigator (Stack)
├── AuthStack (Stack)
│   ├── SplashScreen
│   ├── LoginScreen
│   └── OTPVerificationScreen
└── DriverAppStack (Stack, rendered when authenticated)
    ├── DriverTabNavigator (Bottom Tabs, uses DriverBottomNav)
    │   ├── Tab: Home → HomeScreen
    │   ├── Tab: Trips → TripsScreen
    │   └── Tab: Profile → ProfileScreen
    └── Stack screens (pushed on top of tabs):
        ├── ActiveTripScreen
        ├── LiveNavigationScreen (modal)
        ├── PickupVerificationScreen
        ├── DeliveryVerificationScreen
        ├── TripCompletedScreen
        ├── TripDetailsScreen
        ├── AssignedVehicleScreen
        ├── DocumentsScreen
        ├── NotificationsScreen
        ├── SettingsScreen
        ├── EmergencyScreen (modal)
        └── ReplacementDriverScreen (modal)
```

### Operator App Navigation Structure

```
RootNavigator (Stack)
├── AuthStack (shared with Driver or separate)
└── OperatorAppStack (Stack, rendered when authenticated)
    ├── OperatorTabNavigator (Bottom Tabs, uses OperatorBottomNav)
    │   ├── Tab: Home → HomeScreen (Operator)
    │   ├── Tab: Trips → TripListScreen
    │   ├── Tab: FAB → triggers CreateTripScreen as modal (no tab screen)
    │   ├── Tab: Drivers → DriverListScreen
    │   └── Tab: More → MoreScreen (or direct to VehicleListScreen)
    └── Stack screens:
        ├── TripDetailsScreen (Operator)
        ├── CreateTripScreen (modal)
        ├── DriverDetailsScreen
        ├── AddDriverScreen
        ├── VehicleDetailsScreen
        ├── VehicleRenewalScreen
        ├── InvoiceListScreen
        ├── InvoiceDetailsScreen
        ├── CreateInvoiceScreen
        ├── CustomerListScreen
        ├── CustomerDetailsScreen
        ├── RateCardListScreen
        ├── CreateRateCardScreen
        ├── NotificationsScreen (Operator)
        └── ProfileScreen (Operator)
```

### FAB Behavior

The FAB in `OperatorBottomNav` is not a true navigation tab — it triggers a modal screen:

```typescript
// In OperatorBottomNav
onFabPress={() => navigation.navigate('CreateTripScreen')}

// CreateTripScreen configured as modal in navigator:
<Stack.Screen
  name="CreateTripScreen"
  component={CreateTripScreen}
  options={{ presentation: 'modal' }}
/>
```

### Web Dashboard Navigation

```
App Router / React Router
├── /                → Overview (redirect to /dashboard)
├── /dashboard       → Overview
├── /trips           → TripListScreen
├── /trips/:id       → TripDetailsScreen
├── /trips/create    → CreateTripScreen
├── /drivers         → DriverListScreen
├── /drivers/:id     → DriverDetailsScreen
├── /drivers/add     → AddDriverScreen
├── /vehicles        → VehicleListScreen
├── /vehicles/:id    → VehicleDetailsScreen
├── /vehicles/renewals → VehicleRenewalScreen
├── /customers       → CustomerListScreen
├── /customers/:id   → CustomerDetailsScreen
├── /invoices        → InvoiceListScreen
├── /invoices/:id    → InvoiceDetailsScreen
├── /invoices/create → CreateInvoiceScreen
├── /rate-cards      → RateCardListScreen
├── /rate-cards/create → CreateRateCardScreen
├── /reports/revenue → RevenueReportScreen
├── /reports/performance → PerformanceReportScreen
├── /reports/driver  → DriverReportScreen
├── /reports/vehicle → VehicleReportScreen
├── /settings/general → SettingsGeneral
├── /settings/users  → SettingsUsers
├── /settings/billing → SettingsBilling
├── /settings/integrations → SettingsIntegrations
├── /notifications   → NotificationsScreen
└── /profile         → ProfileScreen
```

---

## Interaction Architecture

### Touch Model (React Native)

All touch handling in React Native screens follows this hierarchy:

1. `TouchableOpacity` for single-tap navigations and actions
2. `Pressable` for fine-grained press state control (if needed)
3. `FlatList` `renderItem` wraps each item in `TouchableOpacity`
4. `onTouchEnd` used only for FilterChip (inherited from Badge component — should be migrated to `TouchableOpacity`)

### Gesture Model

| Gesture | Use Case | Component |
|---------|---------|-----------|
| Tap | Navigation, action triggers | TouchableOpacity |
| Long press | Context menu (future) | TouchableOpacity `onLongPress` |
| Swipe right | Navigate back | React Navigation native gesture |
| Pull down | Dismiss bottom sheet | react-native-reanimated gesture |
| Pull to refresh | Reload list data | FlatList `onRefresh` + `refreshing` |
| Swipe left on list item | Quick actions (future) | react-native-gesture-handler |

---

## Feature Module Architecture

Each major domain is a self-contained module:

```
modules/
├── auth/
│   ├── hooks/useAuth.ts
│   ├── api/authApi.ts
│   └── screens/ (Login, OTP)
│
├── trips/
│   ├── hooks/useTrips.ts, useTripDetails.ts
│   ├── api/tripsApi.ts
│   ├── types/trip.types.ts
│   └── screens/ (List, Details, Create, Active, Verify)
│
├── drivers/
│   ├── hooks/useDrivers.ts, useDriverStatus.ts
│   ├── api/driversApi.ts
│   ├── types/driver.types.ts
│   └── screens/ (List, Details, Add)
│
├── vehicles/
│   ├── hooks/useVehicles.ts
│   ├── api/vehiclesApi.ts
│   ├── types/vehicle.types.ts
│   └── screens/ (List, Details, Renewal)
│
├── invoices/
│   ├── hooks/useInvoices.ts
│   ├── api/invoicesApi.ts
│   ├── types/invoice.types.ts
│   └── screens/ (List, Details, Create)
│
└── customers/
    ├── hooks/useCustomers.ts
    ├── api/customersApi.ts
    ├── types/customer.types.ts
    └── screens/ (List, Details)
```

Each module's API layer uses the same request pattern:
- Base URL from environment variable
- JWT Bearer token from AuthContext
- React Query for caching and revalidation
- Typed responses using TypeScript interfaces from `api-contracts.md`
