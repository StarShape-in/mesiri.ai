# MERCON Developer Guide

## Folder Structure

```
react-native/
├── theme/
│   └── tokens.ts               ← Single source of truth. Import from here only.
├── components/
│   ├── Button.tsx
│   ├── Badge.tsx               ← Badge, StatusBadge, SolidBadge, FilterChip
│   ├── Card.tsx                ← Card, DarkCard
│   ├── Input.tsx               ← Input, SearchInput
│   ├── Avatar.tsx              ← Avatar, AvatarGroup
│   ├── Typography.tsx          ← Heading, Title, Body, Caption, Overline, Mono
│   └── index.ts                ← Barrel export for all components
├── navigation/
│   ├── DriverBottomNav.tsx
│   └── OperatorBottomNav.tsx
├── screens/
│   ├── driver/
│   │   ├── SplashScreen.tsx
│   │   ├── LoginScreen.tsx
│   │   ├── HomeScreen.tsx
│   │   ├── TripsScreen.tsx
│   │   ├── AssignedVehicleScreen.tsx
│   │   ├── DeliveryVerificationScreen.tsx
│   │   ├── DestinationReachedScreen.tsx
│   │   ├── DocumentsScreen.tsx
│   │   ├── EmergencyScreen.tsx
│   │   ├── LiveNavigationScreen.tsx
│   │   ├── NotificationsScreen.tsx
│   │   ├── PickupVerificationScreen.tsx
│   │   ├── ProfileScreen.tsx
│   │   ├── ReplacementDriverScreen.tsx
│   │   ├── SettingsScreen.tsx
│   │   └── TripCompletedScreen.tsx
│   └── operator/
│       ├── HomeScreen.tsx
│       ├── TripListScreen.tsx
│       ├── TripDetailsScreen.tsx
│       ├── CreateTripScreen.tsx
│       ├── DriverListScreen.tsx
│       ├── InvoiceListScreen.tsx
│       ├── VehicleListScreen.tsx
│       └── VehicleRenewalScreen.tsx
└── index.ts                    ← Root barrel export

web/
├── components/                 ← Web-adapted shared components
├── layouts/
│   └── DashboardLayout.tsx     ← Sidebar + main area layout
├── pages/
│   ├── overview/
│   ├── trips/
│   ├── drivers/
│   ├── vehicles/
│   ├── customers/
│   ├── invoices/
│   ├── rate-cards/
│   ├── reports/
│   ├── settings/
│   └── notifications/
└── styles/
    └── tokens.css              ← CSS custom properties from tokens.ts
```

---

## Naming Conventions

### Files
- Components: `PascalCase.tsx` — e.g., `Button.tsx`, `DriverBottomNav.tsx`
- Screens: `[ScreenName]Screen.tsx` — e.g., `HomeScreen.tsx`, `TripDetailsScreen.tsx`
- Tokens: `tokens.ts` (single file, no split)
- Hooks: `use[Name].ts` — e.g., `useTrips.ts`, `useDriverStatus.ts`
- Utilities: `camelCase.ts` — e.g., `formatCurrency.ts`

### Variables and constants
- Design tokens: `PascalCase` object with `camelCase` keys — `Colors.primary`, `Spacing.base`
- Component props: `camelCase` — `iconLeft`, `onTabPress`, `fullWidth`
- Types: `PascalCase` — `ButtonVariant`, `TripStatus`, `AvatarSize`
- StyleSheet keys: `camelCase` — `styles.container`, `styles.iconLeft`

### IDs and codes (as displayed in UI)
- Trip IDs: `TRP-YYYY-NNNN` format — e.g., `TRP-2024-0891`
- Driver IDs: `DRV-NNNN` format — e.g., `DRV-0112`
- Vehicle IDs: `TRK-NNNN` format — e.g., `TRK-2041`
- Invoice IDs: `INV-YYYY-NNNN` format — e.g., `INV-2024-0445`

---

## Component Hierarchy

```
Screen
├── SafeAreaView (always wraps screen)
│   ├── StatusBar
│   ├── Header (View with back button + title)
│   ├── ScrollView or FlatList (content)
│   │   ├── DarkCard (hero/stat sections)
│   │   │   └── Typography helpers
│   │   ├── Card (content sections)
│   │   │   ├── Typography helpers
│   │   │   ├── StatusBadge
│   │   │   ├── Avatar
│   │   │   └── Button
│   │   └── FilterChip row (list screens)
│   └── BottomNav (DriverBottomNav or OperatorBottomNav)
```

---

## Responsive Strategy

### React Native (mobile)
- Use `flex` layouts, not fixed widths
- Use `Dimensions.get('window')` only for layout calculations that truly need screen dimensions (e.g., bottom sheet height, map view)
- Horizontal padding: always `Spacing.base` (16px) minimum on screen edges
- Never use `position: absolute` for content — only for overlays (nav pill, FAB, badges)
- Test on iPhone SE (375pt width) as minimum width and iPhone 14 Pro Max (430pt) as maximum

### Web Dashboard (1440px)
- Sidebar: `width: 240px`, fixed, `position: sticky top-0 height-screen`
- Main content: `margin-left: 240px`, max-width `1200px` centered
- Breakpoints (for web only):
  - `md: 768px` — collapse sidebar to icons-only
  - `lg: 1024px` — show sidebar labels
  - `xl: 1280px` — full layout
  - `2xl: 1536px` — no change from xl
- Grid: 12 columns, 24px gap, at container max-width
- Card widths: 3-col (25%), 4-col (33%), 6-col (50%), 12-col (100%)

---

## Token Usage

### Always import from tokens

```typescript
// Correct
import { Colors, Spacing, Radius, Typography, Shadows } from '../../theme/tokens';

// Wrong — never do this
const ORANGE = '#E8450F';
```

### Token usage in StyleSheet

```typescript
const styles = StyleSheet.create({
  container: {
    backgroundColor: Colors.gray100,     // Never '#F5F5F7'
    padding: Spacing.base,               // Never 16
    borderRadius: Radius['2xl'],         // Never 24
    ...Shadows.sm,                       // Spread shadow object directly
  },
  title: {
    ...Typography.headingL,              // Spread typography token
    color: Colors.dark,                  // Use semantic color token
  },
});
```

### Dynamic styles (variant-driven)

```typescript
// Correct pattern for variant-driven styles (as in Button.tsx)
const variantStyles = {
  primary: { backgroundColor: Colors.primary },
  danger: { backgroundColor: Colors.danger },
};
// Apply as: style={[base.btn, variantStyles[variant]]}

// Wrong — inline ternary color literals
style={{ backgroundColor: variant === 'primary' ? '#E8450F' : '#DC2626' }}
```

---

## State Management Recommendations

### Local state (component-level)
- Use `useState` for: form values, tab selection, search query, toggle states
- Use `useReducer` for: complex form state with multiple related fields (e.g., CreateTrip)

### Server state
- Use React Query (`@tanstack/react-query`) for all API data:
  - `useQuery` for read operations (trip list, driver list, vehicle list)
  - `useMutation` for write operations (create trip, upload document, confirm delivery)
  - Configure `staleTime: 30000` (30 seconds) for list queries
  - Configure `cacheTime: 300000` (5 minutes) for detail queries

### Navigation state
- React Navigation handles navigation state internally
- Do not duplicate navigation state in a global store
- Use route params for passing IDs between screens (not full objects)

### Global state
- Minimal global state via React Context:
  - `AuthContext`: `{ driver/operator: User | null, token: string | null, signIn, signOut }`
  - `ThemeContext`: `{ colorScheme: 'light' | 'dark' }` (reserved for future dark mode)

---

## Animation Implementation

### Basic opacity animation

```typescript
import { Animated } from 'react-native';

const opacity = useRef(new Animated.Value(0)).current;

useEffect(() => {
  Animated.timing(opacity, {
    toValue: 1,
    duration: 200,
    useNativeDriver: true,  // Always true for opacity and transform
  }).start();
}, []);

// Apply: <Animated.View style={{ opacity }}>
```

### Press scale animation

```typescript
const scale = useRef(new Animated.Value(1)).current;

const handlePressIn = () => {
  Animated.timing(scale, {
    toValue: 0.96,
    duration: 150,
    useNativeDriver: true,
  }).start();
};

const handlePressOut = () => {
  Animated.timing(scale, {
    toValue: 1,
    duration: 150,
    useNativeDriver: true,
  }).start();
};
```

### Reduced motion check

```typescript
import { AccessibilityInfo } from 'react-native';
import { useEffect, useState } from 'react';

export function useReducedMotion() {
  const [reduceMotion, setReduceMotion] = useState(false);
  useEffect(() => {
    AccessibilityInfo.isReduceMotionEnabled().then(setReduceMotion);
    const listener = AccessibilityInfo.addEventListener(
      'reduceMotionChanged',
      setReduceMotion
    );
    return () => listener.remove();
  }, []);
  return reduceMotion;
}
```

---

## Accessibility Implementation

### Required on all interactive elements

```typescript
// Buttons
<TouchableOpacity
  accessibilityRole="button"
  accessibilityLabel={label}
  accessibilityState={{ disabled, busy: loading }}
/>

// Navigation tabs
<TouchableOpacity
  accessibilityRole="tab"
  accessibilityLabel={tabLabel}
  accessibilityState={{ selected: isActive }}
/>

// Status badges (non-interactive)
<View accessibilityRole="text" accessibilityLabel={`Status: ${status}`} />

// Images and icons
<Image accessibilityLabel="MERCON logo" />
// OR for decorative icons: accessibilityElementsHidden={true}
```

### Announce dynamic changes

```typescript
import { AccessibilityInfo } from 'react-native';

// After form submission success:
AccessibilityInfo.announceForAccessibility('Trip created successfully');

// After error:
AccessibilityInfo.announceForAccessibility('Error: Please enter a valid phone number');
```

---

## Asset Handling

### Icons (lucide-react-native)

```typescript
import { Home, Truck, User, Plus, Search, Bell, Settings } from 'lucide-react-native';

// Usage
<Home size={20} color={Colors.primary} />
<Truck size={18} color={active ? Colors.primary : 'rgba(255,255,255,0.45)'} />
```

Icon size convention:
- Navigation tabs: 20px (Driver), 18px (Operator)
- Input icons: 16px
- Button icons: 16px for sm/md, 18px for lg
- Card icons: 20px
- Section headers: 20px
- FAB: 22px (use `Plus` icon)

### Font loading

```typescript
// In App.tsx or _layout.tsx (Expo)
import * as Font from 'expo-font';

await Font.loadAsync({
  'PlusJakartaSans-Regular': require('./assets/fonts/PlusJakartaSans-Regular.ttf'),
  'PlusJakartaSans-Medium': require('./assets/fonts/PlusJakartaSans-Medium.ttf'),
  'PlusJakartaSans-SemiBold': require('./assets/fonts/PlusJakartaSans-SemiBold.ttf'),
  'PlusJakartaSans-Bold': require('./assets/fonts/PlusJakartaSans-Bold.ttf'),
  'PlusJakartaSans-ExtraBold': require('./assets/fonts/PlusJakartaSans-ExtraBold.ttf'),
});
```

---

## Code Organization Rules

1. **One component per file.** Exception: closely related components exported from the same file (Badge.tsx exports Badge, StatusBadge, SolidBadge, FilterChip).
2. **StyleSheet at the bottom.** All `StyleSheet.create()` calls go at the bottom of the file, after the component definitions.
3. **Types at the top.** All type/interface definitions go at the top of the file, before imports are used.
4. **No default exports.** Use named exports only. This makes refactoring safer and imports explicit.
5. **No inline styles.** All styles must be in `StyleSheet.create()`. Exception: styles that depend on dynamic values (e.g., `width: `${progress}%``) must be computed inline using token values.
6. **No magic numbers.** Every number in a style must reference a token. Exception: `borderRadius: diameter / 2` for circle elements (Avatar), where `diameter` is itself from a token-derived map.

---

## Testing Recommendations

### Unit tests (Jest + React Native Testing Library)
- Test every component variant renders without crash
- Test disabled state prevents onPress
- Test loading state shows spinner and hides label
- Test StatusBadge resolves correct colors for each status string
- Test FilterChip toggles active state

### Integration tests
- Test complete authentication flow (phone → OTP → home)
- Test Create Trip form validation (all required fields, submit button state)
- Test status filter changes the displayed list

### Visual regression
- Use Storybook for component isolation
- Screenshot tests for: Button (all variants × sizes), Badge (all statuses), Card/DarkCard, Navigation pills

### Device testing matrix
- iOS: iPhone SE (375pt), iPhone 14 (390pt), iPhone 14 Pro Max (430pt)
- Android: Pixel 5 (393pt), Samsung Galaxy S23 (360pt)
- Test VoiceOver on iOS, TalkBack on Android

---

## Performance Recommendations

### List rendering
- Always use `FlatList` for lists longer than 10 items — never `ScrollView` with `.map()`
- Provide `keyExtractor` returning the item's ID string
- Use `getItemLayout` for fixed-height list items to enable scroll-to-index
- Use `initialNumToRender: 10` and `maxToRenderPerBatch: 5`
- Use `removeClippedSubviews: true` on Android

### Images
- Use `resizeMode: 'cover'` for vehicle and driver photos
- Implement lazy loading for image grids (POD photo grid)
- Cache images using `react-native-fast-image`

### Memoization
- Wrap list item components with `React.memo`
- Use `useCallback` for `onPress` handlers passed as props
- Use `useMemo` for filtered/sorted list data derived from raw API data

### Bundle size
- Do not import entire icon libraries — import individual icons from lucide-react-native
- Tree-shake the design token import if only a subset is used in a screen
