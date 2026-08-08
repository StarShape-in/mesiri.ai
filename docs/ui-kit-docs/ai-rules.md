# MERCON AI Agent Rules

These rules are MANDATORY for any AI coding agent working on the MERCON platform. No rule may be overridden, "improved upon", or skipped for convenience. When in doubt, ask rather than guess.

---

## Rule 1 — Never Hardcode Colors

**FORBIDDEN:**
```typescript
color: '#E8450F'
backgroundColor: '#1C1C2E'
borderColor: '#DC2626'
color: 'orange'
color: 'gray'
```

**REQUIRED:**
```typescript
color: Colors.primary
backgroundColor: Colors.darkCard
borderColor: Colors.danger
```

Every color in every file must reference a key from the `Colors` object in `react-native/theme/tokens.ts`. There are no exceptions. If you need a color that does not exist in the Colors object, do not invent it — use the closest existing token or flag the gap.

---

## Rule 2 — Never Hardcode Spacing

**FORBIDDEN:**
```typescript
padding: 16
margin: 8
paddingHorizontal: 24
gap: 12
```

**REQUIRED:**
```typescript
padding: Spacing.base       // 16
margin: Spacing.sm          // 8
paddingHorizontal: Spacing.xl  // 24
gap: Spacing.md             // 12
```

All spacing values must use the `Spacing` object. The only permitted exception is derived expressions like `Spacing.xs + 2` (= 6) or `Spacing.md - 2` (= 10), which appear in the existing Button component. Do not invent new derivations without strong justification.

---

## Rule 3 — Never Hardcode Border Radius

**FORBIDDEN:**
```typescript
borderRadius: 24
borderRadius: 20
borderRadius: 9999
borderRadius: 100
borderRadius: 50
```

**REQUIRED:**
```typescript
borderRadius: Radius['2xl']   // 24 — for cards
borderRadius: Radius.xl       // 20 — for buttons, inputs
borderRadius: Radius.full     // 9999 — for pills, badges, avatars, chips
```

The one permitted exception is `borderRadius: diameter / 2` for Avatar where `diameter` is derived from the SIZE_MAP token.

---

## Rule 4 — Never Hardcode Font Sizes or Weights

**FORBIDDEN:**
```typescript
fontSize: 14
fontWeight: '600'
lineHeight: 22
fontSize: 20, fontWeight: 'bold'
```

**REQUIRED:**
```typescript
...Typography.bodyMedium      // fontSize: 14, fontWeight: '400', lineHeight: 22
...Typography.headingL        // fontSize: 20, fontWeight: '700', lineHeight: 28
```

Always spread a Typography token for text styles. Never write `fontSize`, `fontWeight`, or `lineHeight` as literal numbers in a component's StyleSheet.

---

## Rule 5 — Never Build a Custom Button

**FORBIDDEN:** Creating a new `TouchableOpacity` + `Text` combination that acts as a button.

```typescript
// NEVER DO THIS
<TouchableOpacity style={{ backgroundColor: '#E8450F', borderRadius: 20, padding: 15 }}>
  <Text style={{ color: '#fff', fontWeight: '700' }}>Submit</Text>
</TouchableOpacity>
```

**REQUIRED:**
```typescript
<Button label="Submit" variant="primary" size="lg" onPress={handleSubmit} />
```

The `Button` component supports 6 variants × 3 sizes × disabled × loading × iconLeft × iconRight. If an existing combination does not meet the need, document the gap and discuss — do not build a custom button.

---

## Rule 6 — Never Build a Custom Badge or Status Indicator

**FORBIDDEN:**
```typescript
<View style={{ backgroundColor: '#F0FDF4', borderRadius: 999, padding: 4 }}>
  <Text style={{ color: '#16A34A', fontSize: 12 }}>Completed</Text>
</View>
```

**REQUIRED:**
```typescript
<StatusBadge status="Completed" />
```

For custom non-status badges, use the `Badge` component with explicit `color` and `bg` props. For filter chips, use `FilterChip`. Never manually assign colors to represent status.

---

## Rule 7 — Never Manually Assign Status Colors

**FORBIDDEN:**
```typescript
const color = trip.status === 'Completed' ? '#16A34A' : '#DC2626';
const bg = trip.status === 'In Transit' ? '#EFF6FF' : '#F5F5F7';
```

**REQUIRED:**
```typescript
const { color, bg } = getStatusColors(trip.status);
// Or simply:
<StatusBadge status={trip.status} />
```

The `getStatusColors()` function in `tokens.ts` is the authoritative color resolver for all status strings. It handles all 12 known statuses and returns the correct color pair. It also returns a safe fallback for unknown statuses.

---

## Rule 8 — Never Build a Custom Card Container

**FORBIDDEN:**
```typescript
<View style={{ backgroundColor: '#fff', borderRadius: 24, padding: 16, shadowColor: '#000', ... }}>
```

**REQUIRED:**
```typescript
<Card>
  <View style={{ padding: Spacing.base }}>
    {/* content */}
  </View>
</Card>
```

Use `Card` for light surfaces and `DarkCard` for dark (`#1C1C2E`) surfaces. The `Card` component with `variant="dark"` is also available. Never recreate the card visual styling inline.

---

## Rule 9 — Never Build a Custom Text Component

**FORBIDDEN:**
```typescript
<Text style={{ fontSize: 20, fontWeight: '700', color: '#1A1A1A' }}>Active Trips</Text>
<Text style={{ fontSize: 12, color: '#6E6E80' }}>Last updated</Text>
```

**REQUIRED:**
```typescript
<Heading>Active Trips</Heading>
<Caption color="muted">Last updated</Caption>
```

Use the exported Typography helpers: `Heading`, `Title`, `Body`, `Caption`, `Overline`, `Mono`. The `color` prop accepts semantic role names (`primary`, `secondary`, `muted`, `brand`, `danger`, `success`, `warning`, `white`), not hex values.

---

## Rule 10 — Never Use Emoji in Production Code

The source files contain emoji placeholders (⌂, 🚛, 👤, 🔍) marked as `// TODO: replace with lucide-react-native`. These are development scaffolding.

**FORBIDDEN in production:**
```typescript
<Text style={styles.icon}>🚛</Text>
<Text style={{ color: Colors.gray400, fontSize: 16 }}>🔍</Text>
```

**REQUIRED:**
```typescript
import { Truck, Search } from 'lucide-react-native';
<Truck size={18} color={active ? Colors.primary : 'rgba(255,255,255,0.45)'} />
<Search size={16} color={Colors.gray400} />
```

All icon slots must use `lucide-react-native`. The icon name mapping is documented in `assets.md`.

---

## Rule 11 — Never Override Navigation Component Styles

Do not modify `DriverBottomNav` or `OperatorBottomNav` to change colors, sizes, or layout. If a screen needs a different navigation pattern, document the requirement.

**FORBIDDEN:**
```typescript
// Modifying the nav component to fit a single screen's needs
<DriverBottomNav
  activeTab={activeTab}
  onTabPress={setActiveTab}
  style={{ backgroundColor: Colors.primary }}  // NEVER
/>
```

---

## Rule 12 — Never Invent New Animation Curves or Durations

**FORBIDDEN:**
```typescript
Animated.timing(value, { duration: 250, easing: Easing.elastic(2) })
```

**REQUIRED:** Use only the durations and curves documented in `animations.md`:
- micro: 150ms, ease-out
- fast: 200ms, ease-out
- standard: 300ms, ease-out
- slow: 400ms, ease-out

Spring parameters: damping 15, stiffness 150.

---

## Rule 13 — Never Guess Missing States

If a component or screen has a state (loading, empty, error, offline) that is not yet designed or documented, do not invent a visual treatment. Instead:
1. Implement a minimal placeholder (e.g., `<Body>Loading…</Body>` on a white background)
2. Add a comment: `// TODO: design missing state - [loading|empty|error|offline] state needed`
3. Do not copy styles from another app, system, or training data

---

## Rule 14 — Never Use Default Export

All MERCON components use named exports:

**FORBIDDEN:**
```typescript
export default function Button() {}
```

**REQUIRED:**
```typescript
export function Button() {}
```

This applies to all components, screens, hooks, and utilities.

---

## Rule 15 — Never Import From Component Files Directly in Screens

**FORBIDDEN:**
```typescript
import { Button } from '../../components/Button';
import { StatusBadge } from '../../components/Badge';
```

**REQUIRED:**
```typescript
import { Button, StatusBadge, Card, Avatar } from '../../components';
// or from the root barrel:
import { Button, StatusBadge } from '../..';
```

Always use the barrel export.

---

## Rule 16 — Never Use StyleSheet Outside of the Defining File

Do not pass a StyleSheet from one file to another. Each component owns its own StyleSheet. Sharing styles is done through the token system, not by passing StyleSheet objects.

---

## Rule 17 — Never Create a Card with Internal Padding in the Card Component

The `Card` and `DarkCard` components do not set internal padding. The consuming layout adds padding inside the card.

**FORBIDDEN:**
```typescript
// Modifying Card component to add default padding
<View style={[styles.card, { padding: 16 }, style]}>
```

**REQUIRED:**
```typescript
// In the screen that uses Card:
<Card>
  <View style={{ padding: Spacing.base }}>
    <Title>Section Heading</Title>
  </View>
</Card>
```

---

## Rule 18 — Never Use `position: 'absolute'` for Content Elements

Absolute positioning is only permitted for:
- The online status dot on Avatar
- Floating overlays (modal backdrop, bottom sheet)
- FAB positioning within the navigation pill slot

**FORBIDDEN:**
```typescript
// Absolutely positioning a content element
<View style={{ position: 'absolute', top: 20, left: 16 }}>
  <Text>This should not be absolute</Text>
</View>
```

---

## Rule 19 — Always Respect Touch Target Minimums

Every interactive element must have an effective touch target of at least 44×44pt. If a component is visually smaller, add padding to reach 44pt.

**FORBIDDEN:**
```typescript
// Tiny tappable icon with no padding
<TouchableOpacity onPress={handleBack}>
  <ArrowLeft size={16} color={Colors.dark} />
</TouchableOpacity>
```

**REQUIRED:**
```typescript
<TouchableOpacity
  onPress={handleBack}
  style={{ padding: Spacing.md, margin: -Spacing.md }}  // Visual size preserved, touch area expanded
>
  <ArrowLeft size={20} color={Colors.dark} />
</TouchableOpacity>
```

---

## Rule 20 — Never Add Text That Is Not in the Design Specification

Do not invent placeholder copy, section headings, button labels, or instructional text that is not specified in `screens.md` or the source screen files. If copy is missing, use `[COPY NEEDED]` as a placeholder and flag it.

---

## Rule 21 — Tokens Are Read-Only

Do not modify `tokens.ts` to add, remove, or change any value without explicit instruction. The token file is the contract between design and engineering. Any modification without a corresponding design decision is unauthorized.

**FORBIDDEN:**
- Adding a `Colors.primaryMedium` value because you think you need it
- Changing `Radius['2xl']` from 24 to 20 because a component "looks better"
- Adding a `Spacing['6xl']` value because 64px is not enough

---

## Rule 22 — Always Handle All Status Strings Case-Sensitively

The `getStatusColors()` function uses exact string matching. Status strings are case-sensitive:
- `'Completed'` — capital C ✓
- `'completed'` — lowercase fails, returns fallback ✗
- `'In Transit'` — space in the middle ✓
- `'InTransit'` — no space fails ✗

When passing status strings to `StatusBadge`, always use the exact casing as defined in `TripStatus`, `VehicleStatus`, and `DocStatus` types.

---

## Rule 23 — Never Use `flex: 1` on a Screen Root Without `SafeAreaView`

Every screen root must be:
```typescript
<SafeAreaView style={{ flex: 1, backgroundColor: Colors.gray100 }}>
```

Never use a plain `<View style={{ flex: 1 }}>` as a screen root.

---

## Rule 24 — Never Hardcode the Navigation Pill Background

The navigation pill background color is `Colors.navBg`, which equals `#1C1C2E`. It is semantically different from `Colors.darkCard` even though they share the same hex value. Use `Colors.navBg` for navigation and `Colors.darkCard` for card surfaces.

---

## Rule 25 — Test on iPhone SE Before Claiming Completion

Before considering any mobile screen complete:
- Render it at 375pt width (iPhone SE)
- Verify no horizontal overflow
- Verify no text truncation of critical information (trip ID, status, ETA)
- Verify the navigation pill does not extend beyond the screen width

If you cannot run the app, verify that no fixed width in the layout exceeds 343pt (375 - 32 minimum padding).

---

## Summary of What You MAY Do

- Create new screen files following the established pattern (SafeAreaView + ScrollView/FlatList + BottomNav)
- Add new features using only existing components and tokens
- Extend a component's props with optional additions that do not change default behavior
- Add new icon imports from `lucide-react-native`
- Add new screen-level styles using only token values
- Add `accessibilityLabel`, `accessibilityRole`, and `accessibilityHint` props to any element
- Write `useQuery` and `useMutation` hooks for new API endpoints following existing patterns

## Summary of What You MAY NOT Do

- Hardcode any color, spacing, radius, font size, or font weight
- Create custom buttons, badges, cards, or inputs
- Modify `tokens.ts` without explicit instruction
- Use any icon library other than lucide-react-native
- Use emoji as icons in any component
- Invent new animation durations, curves, or interaction patterns
- Assign status colors manually without `getStatusColors()`
- Import from component files directly instead of using the barrel export
- Add default exports
- Use `position: 'absolute'` for content elements
- Skip accessibility attributes on interactive elements
