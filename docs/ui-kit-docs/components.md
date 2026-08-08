# MERCON Component Library

Every component in the MERCON design system is documented here. This is the authoritative reference for all component variants, props, states, tokens, and behavior.

---

## Button

**File:** `react-native/components/Button.tsx`
**Purpose:** The primary interactive element for all user actions. All tappable call-to-action elements must use this component.

### Variants

| Variant | Background | Text Color | Border | Shadow |
|---------|-----------|------------|--------|--------|
| `primary` | `#E8450F` | `#FFFFFF` | none | `Shadows.primary` (orange glow) |
| `secondary` | `#F5F5F7` | `#1A1A1A` | none | none |
| `outline` | transparent | `#E8450F` | 2px `#E8450F` | none |
| `ghost` | transparent | `#E8450F` | none | none |
| `danger` | `#DC2626` | `#FFFFFF` | none | none |
| `success` | `#16A34A` | `#FFFFFF` | none | none |

### Sizes

| Size | Horizontal Padding | Vertical Padding | Typography Token |
|------|-------------------|-----------------|-----------------|
| `sm` | `Spacing.md` (12px) | `Spacing.xs + 2` (6px) | `buttonSmall` — 12px/600 |
| `md` | `Spacing.lg` (20px) | `Spacing.md - 2` (10px) | `buttonMedium` — 14px/600 |
| `lg` | `Spacing.xl` (24px) | `Spacing.base - 1` (15px) | `buttonLarge` — 16px/700 |

### States

| State | Visual Treatment |
|-------|-----------------|
| Default | Full opacity, shadow as per variant |
| Pressed | `activeOpacity: 0.82` (handled by TouchableOpacity) |
| Disabled | `opacity: 0.45`, `disabled: true` on TouchableOpacity |
| Loading | Label replaced by `ActivityIndicator` (small size, white for primary/danger/success, orange for others) |

### Props

```typescript
interface ButtonProps {
  label: string;           // Required. Button text.
  onPress?: () => void;    // Touch handler
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger' | 'success'; // Default: 'primary'
  size?: 'sm' | 'md' | 'lg'; // Default: 'md'
  disabled?: boolean;      // Disables touch and dims to 0.45 opacity
  loading?: boolean;       // Shows spinner, disables touch
  iconLeft?: React.ReactNode;  // Icon placed before label, margin-right: 8px
  iconRight?: React.ReactNode; // Icon placed after label, margin-left: 8px
  fullWidth?: boolean;     // width: '100%'
  style?: ViewStyle;       // Override container styles (use sparingly)
}
```

### Layout

- `flexDirection: 'row'`
- `alignItems: 'center'`
- `justifyContent: 'center'`
- `borderRadius: Radius.xl` (20px) — applied to all variants and sizes

### Tokens Used

`Colors.primary`, `Colors.primaryDark`, `Colors.white`, `Colors.gray100`, `Colors.dark`, `Colors.danger`, `Colors.success`, `Spacing.xs`, `Spacing.sm`, `Spacing.md`, `Spacing.lg`, `Spacing.xl`, `Spacing.base`, `Radius.xl`, `Typography.buttonLarge`, `Typography.buttonMedium`, `Typography.buttonSmall`, `Shadows.primary`

### Accessibility

- Minimum touch target height from padding: ~44pt for `md` and `lg` sizes
- `disabled` prop passes through to TouchableOpacity `disabled` prop
- Loading state must be announced via `accessibilityLabel` (e.g., "Loading, please wait")

### Implementation Notes

- Never use raw `TouchableOpacity` + `Text` for a button — always use this component
- The `primary` variant is the default and receives `Shadows.primary` automatically
- When `loading` is true, the label text disappears and is replaced by the spinner
- The `fullWidth` prop sets `width: '100%'` on the container — do not set width on the button directly

---

## Badge

**File:** `react-native/components/Badge.tsx`
**Purpose:** Pill-shaped label for status indication, categorization, and filtering.

### Components in this file

#### `Badge` (generic)

Manual color control for custom badge uses.

```typescript
interface BadgeProps {
  label: string;
  color?: string;   // Text/dot color. Default: Colors.statusPending (#6E6E80)
  bg?: string;      // Background color. Default: Colors.statusPendingBg (#F5F5F7)
  dot?: boolean;    // Show colored dot before label
  style?: ViewStyle;
}
```

Layout: `paddingHorizontal: Spacing.sm + 2` (10px), `paddingVertical: Spacing.xs / 2` (2px), `borderRadius: Radius.full`

Dot: 6×6px circle, `borderRadius: 3`

Text: `Typography.caption` (12px/400/18px lineHeight) with `fontWeight: '600'` override

#### `StatusBadge` (auto-color from status string)

**Preferred component for all status displays.** Pass the status string and colors resolve automatically via `getStatusColors()`.

```typescript
interface StatusBadgeProps {
  status: string; // 'Completed' | 'In Transit' | 'Delayed' | 'Cancelled' | 'Pending' | 'Available' | 'On Trip' | 'Maintenance' | 'Inactive' | 'Active' | 'Expiring' | 'Expired'
  dot?: boolean;
  style?: ViewStyle;
}
```

#### `SolidBadge` (filled background)

For priority indicators or alerts where a solid filled pill is needed.

```typescript
interface SolidBadgeProps {
  label: string;
  color?: string; // Background color. Default: Colors.danger
  style?: ViewStyle;
}
```

Text is always white (`Colors.white`).

#### `FilterChip` (toggleable)

For filter rows above lists. Active state fills with `Colors.primary` orange; inactive state uses `Colors.gray100`.

```typescript
interface FilterChipProps {
  label: string;
  active?: boolean;
  onPress?: () => void;
  style?: ViewStyle;
}
```

Layout: `paddingHorizontal: Spacing.md` (12px), `paddingVertical: Spacing.xs + 1` (5px), `borderRadius: Radius.full`

Text: `Typography.bodySmall` (13px/400/20px) with `fontWeight: '600'`, color `Colors.white` when active, `Colors.dark` when inactive.

### Tokens Used

`Colors.primary`, `Colors.white`, `Colors.dark`, `Colors.gray100`, `Colors.statusPending`, `Colors.statusPendingBg`, `Spacing.xs`, `Spacing.sm`, `Spacing.md`, `Radius.full`, `Typography.caption`, `Typography.bodySmall`

### Status Color Resolution

All StatusBadge color decisions come from `getStatusColors(status)` in `tokens.ts`. Never manually assign status colors in components.

---

## Card

**File:** `react-native/components/Card.tsx`
**Purpose:** Surface container for all content groups. All content must live inside a Card or DarkCard.

### Components in this file

#### `Card`

White surface container with subtle border and shadow.

```typescript
interface CardProps {
  children: React.ReactNode;
  style?: ViewStyle;
  variant?: 'default' | 'dark'; // Default: 'default'
  elevated?: boolean; // Default: false. true → Shadows.md, false → Shadows.sm
}
```

Default styles:
- `backgroundColor: '#FFFFFF'`
- `borderRadius: Radius['2xl']` (24px)
- `borderWidth: 1`
- `borderColor: 'rgba(0,0,0,0.07)'`
- `overflow: 'hidden'`

Dark variant overrides:
- `backgroundColor: '#1C1C2E'`
- `borderColor: 'transparent'`

#### `DarkCard`

Always dark (`#1C1C2E`) card with `Shadows.md`. Used for dashboard stat cards and dark header panels.

```typescript
interface DarkCardProps {
  children: React.ReactNode;
  style?: ViewStyle;
}
```

Styles: `backgroundColor: '#1C1C2E'`, `borderRadius: Radius['2xl']` (24px), `overflow: 'hidden'`, `Shadows.md`

### Tokens Used

`Colors.white`, `Colors.darkCard`, `Radius['2xl']`, `Shadows.sm`, `Shadows.md`

### Layout Notes

- Cards do not set internal padding — the consuming layout must add padding inside
- Cards use `overflow: 'hidden'` to clip child content to the rounded corners
- Never nest a Card inside another Card

---

## Input

**File:** `react-native/components/Input.tsx`
**Purpose:** Text entry for forms, searches, and data input.

### Components in this file

#### `Input`

Full-featured labeled text input with state-driven visual feedback.

```typescript
interface InputProps {
  label?: string;
  value?: string;
  onChangeText?: (text: string) => void;
  placeholder?: string;
  state?: 'default' | 'focused' | 'error' | 'success' | 'disabled'; // Default: 'default'
  errorText?: string;    // Shown below input when state === 'error'
  successText?: string;  // Shown below input when state === 'success'
  iconLeft?: React.ReactNode;
  iconRight?: React.ReactNode;
  secureTextEntry?: boolean;
  keyboardType?: KeyboardTypeOptions;
  multiline?: boolean;
  numberOfLines?: number;
  style?: ViewStyle;     // Applied to wrapper
}
```

**Container base styles:**
- `flexDirection: 'row'`
- `alignItems: 'center'`
- `paddingHorizontal: Spacing.base` (16px)
- `borderRadius: Radius.xl` (20px)
- `borderWidth: 2`
- `borderColor: 'transparent'` (default)
- `backgroundColor: Colors.gray100` (`#F5F5F7`)
- `minHeight: 48`

**State overrides:**

| State | Background | Border Color |
|-------|-----------|--------------|
| `default` | `#F5F5F7` | transparent |
| `focused` | `#F5F5F7` | `#E8450F40` (orange 25% opacity) |
| `error` | `#FEF2F2` | `#DC262640` (red 25% opacity) |
| `success` | `#F0FDF4` | `#16A34A40` (green 25% opacity) |
| `disabled` | `#F5F5F7` | transparent, `opacity: 0.5` |

**Internal input:**
- `flex: 1`
- `Typography.bodyMedium` (14px/400/22px)
- `color: Colors.dark`
- `paddingVertical: Spacing.md - 2` (10px)
- Placeholder color: `Colors.gray400` (`#9898A4`)

**Label:** `Typography.bodySmall` (13px/400/20px) with `fontWeight: '600'`, `color: Colors.dark`

**Helper text:** `Typography.caption` (12px/400/18px). Error text: `Colors.danger`. Success text: `Colors.success`.

**Multiline:** `minHeight: 80`, `textAlignVertical: 'top'`

**Focus behavior:** Input internally tracks `focused` state. When `state === 'default'` and focused, effective state becomes `focused`. When `state` is explicitly set to `error` or `success`, focus does not override it.

#### `SearchInput`

Simplified search bar with left icon slot.

```typescript
interface SearchInputProps {
  value?: string;
  onChangeText?: (t: string) => void;
  placeholder?: string; // Default: 'Search…'
  style?: ViewStyle;
}
```

Styles: `backgroundColor: Colors.gray100`, `borderRadius: Radius.xl` (20px), `paddingHorizontal: Spacing.md` (12px), `height: 44`

Icon slot: left-aligned, `marginRight: Spacing.sm` (8px). Use lucide `Search` icon, size 16, color `Colors.gray400`.

### Tokens Used

`Colors.dark`, `Colors.gray100`, `Colors.gray400`, `Colors.dangerLight`, `Colors.successLight`, `Colors.danger`, `Colors.success`, `Colors.primary`, `Spacing.xs`, `Spacing.sm`, `Spacing.md`, `Spacing.base`, `Radius.xl`, `Typography.bodySmall`, `Typography.bodyMedium`, `Typography.caption`

---

## Avatar

**File:** `react-native/components/Avatar.tsx`
**Purpose:** User, driver, and customer representation via initials with optional online status indicator.

### `Avatar`

```typescript
interface AvatarProps {
  initials: string;           // 1-2 characters, typically first letters of name
  color?: string;             // Background color. Default: Colors.primary (#E8450F)
  size?: 'sm' | 'md' | 'lg' | 'xl'; // Default: 'md'
  onlineStatus?: 'online' | 'busy' | 'offline';
  style?: ViewStyle;
}
```

**Size map:**

| Size | Diameter | Font Size | Dot Size |
|------|---------|-----------|---------|
| `sm` | 28px | 10px | 8px |
| `md` | 36px | 12px | 10px |
| `lg` | 48px | 14px | 12px |
| `xl` | 64px | 18px | 14px |

**Online status dot colors:**

| Status | Color |
|--------|-------|
| `online` | `Colors.success` (`#16A34A`) |
| `busy` | `Colors.warning` (`#D97706`) |
| `offline` | `Colors.gray400` (`#9898A4`) |

Dot position: `bottom: 0, right: 0`, `borderWidth: 2, borderColor: Colors.white`

Initials text: `fontWeight: '700'`, `color: Colors.white`

### `AvatarGroup`

Stacks avatars horizontally with -8px left overlap. Shows overflow count in a gray circle.

```typescript
interface AvatarGroupProps {
  items: { initials: string; color?: string }[];
  max?: number; // Default: 5. Items beyond max shown as "+N"
}
```

Overflow circle: `width: 36, height: 36, borderRadius: 18, backgroundColor: Colors.gray200`, `borderWidth: 2, borderColor: Colors.white`

Overflow text: `fontSize: 12, fontWeight: '700', color: Colors.gray500`

### Tokens Used

`Colors.primary`, `Colors.white`, `Colors.success`, `Colors.warning`, `Colors.gray400`, `Colors.gray200`, `Colors.gray500`, `Radius.full`

---

## Typography

**File:** `react-native/components/Typography.tsx`
**Purpose:** Semantic text helpers that apply the correct type style and color in one import.

### Exported components

| Component | Type Token | Default Color |
|-----------|-----------|---------------|
| `Heading` | `T.headingL` (20px/700/28px) | `Colors.dark` (primary) |
| `Title` | `T.headingS` (16px/600/24px) | `Colors.dark` (primary) |
| `Body` | `T.bodyMedium` (14px/400/22px) | `Colors.dark` (primary) |
| `Caption` | `T.caption` (12px/400/18px) | `Colors.gray500` (muted) |
| `Overline` | `T.overline` (11px/600/1px tracking/16px lh) | `Colors.gray500` (muted), `textTransform: 'uppercase'` |
| `Mono` | `T.mono` (12px/monospace/600) | `Colors.primary` (brand) |

### Props (all components)

```typescript
interface TypoProps {
  children: React.ReactNode;
  color?: 'primary' | 'secondary' | 'muted' | 'brand' | 'danger' | 'success' | 'warning' | 'white';
  style?: TextStyle;
  numberOfLines?: number;
}
```

### Color Map

| Prop Value | Resolved Color |
|------------|---------------|
| `primary` | `#1A1A1A` |
| `secondary` | `#3B3B44` |
| `muted` | `#6E6E80` |
| `brand` | `#E8450F` |
| `danger` | `#DC2626` |
| `success` | `#16A34A` |
| `warning` | `#D97706` |
| `white` | `#FFFFFF` |

### Usage

```tsx
// Correct
<Heading>Active Trips</Heading>
<Caption color="muted">Last updated 2 min ago</Caption>
<Mono>TRP-2024-0891</Mono>

// Wrong — never do this
<Text style={{ fontSize: 20, fontWeight: '700', color: '#1A1A1A' }}>Active Trips</Text>
```

---

## DriverBottomNav

**File:** `react-native/navigation/DriverBottomNav.tsx`
**Purpose:** Bottom tab navigation for the Driver App. Dark floating pill with 3 tabs.

### Structure

- **Outer wrapper:** `paddingHorizontal: 24, paddingBottom: 24, paddingTop: 8`
- **Pill container:** `backgroundColor: '#1C1C2E'`, `borderRadius: Radius.full` (9999), `paddingHorizontal: 16, paddingVertical: 10`, `Shadows.nav`
- **Tabs:** 3 — Home, Trips, Profile
- **Active tab:** icon and label both `Colors.primary` (`#E8450F`)
- **Inactive tab:** `rgba(255,255,255,0.45)` for both icon and label
- **Icon size:** 20px (replace emoji with lucide icon)
- **Label size:** 9px, `fontWeight: '600'`
- **Tab padding:** `paddingVertical: Spacing.xs` (4px)
- **Gap between icon and label:** 2px

### Props

```typescript
interface DriverBottomNavProps {
  activeTab: 'Home' | 'Trips' | 'Profile';
  onTabPress: (tab: 'Home' | 'Trips' | 'Profile') => void;
}
```

### Icon Mapping (lucide-react-native)

| Tab | Lucide Icon |
|-----|------------|
| Home | `Home` |
| Trips | `Truck` |
| Profile | `User` |

---

## OperatorBottomNav

**File:** `react-native/navigation/OperatorBottomNav.tsx`
**Purpose:** Bottom tab navigation for the Operator App. Dark floating pill with 4 tabs and a center FAB.

### Structure

- **Outer wrapper:** `paddingHorizontal: 16, paddingBottom: 24, paddingTop: 8`
- **Pill container:** `backgroundColor: '#1C1C2E'`, `borderRadius: Radius.full`, `paddingHorizontal: 12, paddingVertical: 8`, `Shadows.nav`
- **Layout:** [Home] [Trips] [FAB] [Drivers] [More]
- **Left tabs:** Home, Trips
- **Right tabs:** Drivers, More
- **Active tab:** `Colors.primary` for icon and label
- **Inactive tab:** `rgba(255,255,255,0.45)`
- **Icon size:** 18px
- **Label size:** 9px, `fontWeight: '600'`

### FAB Specification

- **Size:** 48×48px
- **Border radius:** 24px (full circle)
- **Background:** `Colors.white` (`#FFFFFF`)
- **Border:** `borderWidth: 2`, `borderColor: Colors.primary` (`#E8450F`)
- **Icon:** `+` character, 22px, `Colors.primary`, `fontWeight: '700'`, `lineHeight: 24`
- **Shadow:** `Shadows.sm`
- **Position:** centered in pill via `fabSlot: { flex: 1, alignItems: 'center' }`

### Props

```typescript
interface OperatorBottomNavProps {
  activeTab: 'Home' | 'Trips' | 'Drivers' | 'More';
  onTabPress: (tab: 'Home' | 'Trips' | 'Drivers' | 'More') => void;
  onFabPress?: () => void; // Opens CreateTrip flow
}
```

### Icon Mapping (lucide-react-native)

| Tab | Lucide Icon |
|-----|------------|
| Home | `Home` |
| Trips | `Truck` |
| FAB | `Plus` |
| Drivers | `Users` |
| More | `MoreHorizontal` |

---

## Component Index

All components are exported from `react-native/components/index.ts` and re-exported from `react-native/index.ts`. Import using:

```typescript
import { Button, Badge, StatusBadge, FilterChip, SolidBadge, Card, DarkCard, Input, SearchInput, Avatar, AvatarGroup, Heading, Title, Body, Caption, Overline, Mono } from '../components';
```

Or from the root:

```typescript
import { Button, StatusBadge, Card } from '../../index';
```
