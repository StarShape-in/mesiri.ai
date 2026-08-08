# MERCON Design Language

## Brand Principles

**Clarity first.** Every screen must communicate its primary purpose within 2 seconds. Information hierarchy is established through color, weight, and size — not decoration.

**Orange means action.** `#E8450F` (MERCON Orange) is reserved exclusively for interactive elements: primary buttons, active navigation states, FAB borders, progress fills, hyperlinks, and brand marks. It does not appear as a background fill except in primary buttons, nor as a decorative element.

**Dark anchors light.** The `#1C1C2E` dark navy surfaces appear in navigation, header cards, and dashboard stats. This creates natural visual anchors that tell the user where they are and what matters most. Light gray backgrounds (`#F5F5F7`) and white cards (`#FFFFFF`) hold the content between these anchors.

**Status is legible at a glance.** The five-color status system (green, blue, amber, red, gray) maps directly to operational states. Drivers and operators must be able to read trip and vehicle status without reading the label text.

---

## Typography Philosophy

All text in MERCON uses **Plus Jakarta Sans**. It is a geometric sans-serif with high legibility at small sizes, making it ideal for dense logistics data. Monospace is reserved for IDs and codes only.

The type scale has 15 styles organized into 6 categories:

### Display Styles (for splash screens, hero numbers)

| Token | Size | Weight | Line Height | Letter Spacing |
|-------|------|--------|-------------|----------------|
| `displayLarge` | 40px | 800 | 48px | -0.5 |
| `displayMedium` | 32px | 800 | 40px | -0.5 |
| `displaySmall` | 28px | 700 | 36px | — |

### Heading Styles (for screen titles, section headers)

| Token | Size | Weight | Line Height |
|-------|------|--------|-------------|
| `headingXL` | 24px | 700 | 32px |
| `headingL` | 20px | 700 | 28px |
| `headingM` | 18px | 600 | 26px |
| `headingS` | 16px | 600 | 24px |

### Body Styles (for content, labels, metadata)

| Token | Size | Weight | Line Height |
|-------|------|--------|-------------|
| `bodyLarge` | 16px | 400 | 26px |
| `bodyMedium` | 14px | 400 | 22px |
| `bodySmall` | 13px | 400 | 20px |

### Label Styles (for captions, overlines, supplementary text)

| Token | Size | Weight | Line Height | Letter Spacing |
|-------|------|--------|-------------|----------------|
| `caption` | 12px | 400 | 18px | — |
| `overline` | 11px | 600 | 16px | 1px |

### Button Styles (used exclusively inside Button component)

| Token | Size | Weight | Line Height |
|-------|------|--------|-------------|
| `buttonLarge` | 16px | 700 | 16px |
| `buttonMedium` | 14px | 600 | 14px |
| `buttonSmall` | 12px | 600 | 12px |

### Mono (for trip IDs, vehicle IDs, driver IDs, codes)

| Token | Size | Family | Weight |
|-------|------|--------|--------|
| `mono` | 12px | monospace | 600 |

### Typography Color Map

The Typography component exposes a `color` prop mapped to semantic roles:

| Role | Color | Hex |
|------|-------|-----|
| `primary` | Dark text | `#1A1A1A` |
| `secondary` | Medium text | `#3B3B44` |
| `muted` | Subdued text | `#6E6E80` |
| `brand` | MERCON Orange | `#E8450F` |
| `danger` | Error / cancelled | `#DC2626` |
| `success` | Complete / available | `#16A34A` |
| `warning` | Delayed / expiring | `#D97706` |
| `white` | Reversed text | `#FFFFFF` |

---

## Color Philosophy

### Primary Palette

| Token | Hex | Usage |
|-------|-----|-------|
| `Colors.primary` | `#E8450F` | Primary buttons, active states, brand accent |
| `Colors.primaryLight` | `#FFF0EB` | Primary button hover backgrounds, tinted surfaces |
| `Colors.primaryDark` | `#C7380A` | Primary button pressed state, deep orange |

### Neutral Palette

| Token | Hex | Usage |
|-------|-----|-------|
| `Colors.black` | `#111111` | Maximum contrast text |
| `Colors.dark` | `#1A1A1A` | Default body text, headings on light backgrounds |
| `Colors.darkCard` | `#1C1C2E` | Dark card surfaces, navigation pill background |
| `Colors.gray900` | `#111111` | Alias for black |
| `Colors.gray700` | `#3B3B44` | Secondary text |
| `Colors.gray500` | `#6E6E80` | Muted/placeholder text |
| `Colors.gray400` | `#9898A4` | Input placeholder, inactive icons |
| `Colors.gray300` | `#D8D8DC` | Dividers, borders |
| `Colors.gray200` | `#EBEBED` | Avatar overflow background |
| `Colors.gray100` | `#F5F5F7` | Page background, secondary button bg, input bg |
| `Colors.gray50` | `#FAFAFA` | Subtle section backgrounds |
| `Colors.white` | `#FFFFFF` | Card surfaces, reversed text, FAB background |

### Semantic Palette

| Token | Hex | Usage |
|-------|-----|-------|
| `Colors.success` | `#16A34A` | Success states, completed status, available status |
| `Colors.successLight` | `#F0FDF4` | Success input background, success badge background |
| `Colors.successBorder` | `#BBF7D0` | Success input border tint |
| `Colors.warning` | `#D97706` | Warning states, delayed status, expiring documents |
| `Colors.warningLight` | `#FFFBEB` | Warning badge background |
| `Colors.danger` | `#DC2626` | Error states, cancelled status, expired documents |
| `Colors.dangerLight` | `#FEF2F2` | Error input background, danger badge background |
| `Colors.info` | `#2563EB` | In Transit status, informational states |
| `Colors.infoLight` | `#EFF6FF` | Info badge background |
| `Colors.purple` | `#7C3AED` | Special highlights (rate cards, premium indicators) |
| `Colors.purpleLight` | `#F5F3FF` | Purple badge background |

### Navigation Color

| Token | Hex | Usage |
|-------|-----|-------|
| `Colors.navBg` | `#1C1C2E` | Both navigation pill backgrounds (same as darkCard) |

### Status Color System

The status system maps operational states to color pairs (foreground + background):

| Status String | Foreground | Background |
|--------------|------------|------------|
| `Completed` | `#16A34A` | `#F0FDF4` |
| `In Transit` | `#2563EB` | `#EFF6FF` |
| `Delayed` | `#D97706` | `#FFFBEB` |
| `Cancelled` | `#DC2626` | `#FEF2F2` |
| `Pending` | `#6E6E80` | `#F5F5F7` |
| `Available` | `#16A34A` | `#F0FDF4` |
| `On Trip` | `#2563EB` | `#EFF6FF` |
| `Maintenance` | `#D97706` | `#FFFBEB` |
| `Inactive` | `#6E6E80` | `#F5F5F7` |
| `Active` | `#16A34A` | `#F0FDF4` |
| `Expiring` | `#D97706` | `#FFFBEB` |
| `Expired` | `#DC2626` | `#FEF2F2` |
| Unknown/fallback | `#6E6E80` | `#F5F5F7` |

---

## Spacing Philosophy

MERCON uses an **8pt base grid**. All spacing values are multiples of 4.

| Token | Value | Common Usage |
|-------|-------|--------------|
| `Spacing.xs` | 4px | Gap between icon and dot, tight internal gaps |
| `Spacing.sm` | 8px | Icon margins, tab gaps, tight padding |
| `Spacing.md` | 12px | Filter chip padding, input icon margins, section gaps |
| `Spacing.base` | 16px | Default horizontal screen padding, standard padding |
| `Spacing.lg` | 20px | Button horizontal padding (lg size), list item gaps |
| `Spacing.xl` | 24px | Navigation pill horizontal padding, section headers |
| `Spacing['2xl']` | 32px | Large section spacing, card internal padding |
| `Spacing['3xl']` | 40px | Generous section gaps |
| `Spacing['4xl']` | 48px | Full-width button heights, large spacing |
| `Spacing['5xl']` | 64px | Hero spacing, splash screen elements |

**Rules:**
- Never use a value outside this scale
- Never use odd numbers (3px, 5px, 7px, etc.) unless applying a micro-adjustment derived from this scale (e.g., `Spacing.xs + 2 = 6`)
- Horizontal screen padding is always `Spacing.base` (16px) minimum

---

## Border Radius

| Token | Value | Common Usage |
|-------|-------|--------------|
| `Radius.xs` | 4px | Tight corners, table cells |
| `Radius.sm` | 8px | Small chips, compact badges |
| `Radius.md` | 12px | Medium elements |
| `Radius.lg` | 16px | Larger elements |
| `Radius.xl` | 20px | **Buttons** (all sizes), inputs |
| `Radius['2xl']` | 24px | **Cards** (Card, DarkCard) |
| `Radius['3xl']` | 32px | Large pill elements |
| `Radius.full` | 9999px | **Navigation pills**, badges, avatars, filter chips |

---

## Elevation and Shadows

MERCON uses five shadow levels:

| Token | Usage |
|-------|-------|
| `Shadows.sm` | Default card elevation: offset (0,1), opacity 6%, radius 3, elevation 2 |
| `Shadows.md` | Elevated card, DarkCard: offset (0,4), opacity 8%, radius 12, elevation 4 |
| `Shadows.lg` | Modal, bottom sheet: offset (0,8), opacity 12%, radius 24, elevation 8 |
| `Shadows.primary` | Primary button glow: orange shadow, offset (0,4), opacity 35%, radius 12, elevation 6 |
| `Shadows.nav` | Navigation pill: dark shadow, offset (0,8), opacity 45%, radius 24, elevation 12 |

**Rule:** Primary buttons always receive `Shadows.primary`. Navigation pills always receive `Shadows.nav`. Cards receive `Shadows.sm` (default) or `Shadows.md` (when elevated prop is true).

---

## Motion Philosophy

- **Default duration:** 200ms
- **Default curve:** ease-out
- **Minimum duration:** 150ms (micro-interactions: tap highlight, toggle)
- **Maximum duration:** 400ms (page transitions, modal entry)
- **No motion for:** simple state swaps (status badge color change, text updates)
- **Use motion for:** entry/exit of elements, position changes, scale changes, opacity changes

Timing by interaction type:
- Tap/press feedback: 150ms ease-out
- Button press scale: 150ms ease-out, scale 0.96
- Input focus ring: 200ms ease-out
- Badge status change: 200ms ease-in-out (cross-fade)
- Bottom sheet entry: 300ms ease-out (slide up)
- Page transition: 300ms ease-out
- Modal overlay: 250ms ease-out
- Toast/snackbar: 300ms ease-out entry, 200ms ease-in exit

---

## Interaction Philosophy

- All interactive elements respond visually within 100ms of touch
- Touch targets are minimum 44×44pt
- Active opacity for TouchableOpacity is `0.82` for primary/danger/success buttons, `0.7` for navigation tabs, `0.85` for FAB, `0.8` for card rows
- Disabled elements use `opacity: 0.45` — they are never hidden, only dimmed
- Loading states replace button label with ActivityIndicator (never show both)
- Error states never clear automatically — the user must correct the input

---

## Layout Philosophy

**Mobile (Driver App + Operator App):**
- Screen background: `Colors.gray100` (`#F5F5F7`)
- SafeAreaView wraps every screen
- Horizontal padding: `Spacing.base` (16px) minimum
- Bottom navigation sits in a floating pill above safe area inset
- Scroll views use `contentContainerStyle` for consistent padding
- No fixed heights on content containers — use flex

**Web Dashboard (1440px):**
- Sidebar navigation: fixed left, dark (`#1C1C2E`)
- Content area: right of sidebar, `Colors.gray100` background
- Max content width: 1200px with auto horizontal margins
- Grid: 12 columns, 24px gutter
- Cards span 3, 4, 6, or 12 columns depending on content density

---

## Accessibility Philosophy

- Minimum contrast ratio: 4.5:1 for body text (WCAG AA)
- Minimum contrast ratio: 3:1 for large text (18px+ bold or 24px+)
- Touch targets: minimum 44×44pt (never compromise below 36pt)
- Focus indicators: visible on all interactive elements for web keyboard navigation
- Dynamic type: body text should scale with system font size settings
- Reduced motion: respect `AccessibilityInfo.isReduceMotionEnabled`
- Color: never convey information by color alone — always pair with a label

---

## Design Constraints

- Plus Jakarta Sans is the only permitted font family (except monospace for IDs)
- All colors must come from the Colors token object — no hex literals in components
- Spacing must come from the Spacing token object — no numeric literals in components
- Border radius must come from the Radius token object — no numeric literals in components
- Icons must come from `lucide-react-native` — no emoji icons in production code
- Status colors must resolve through `getStatusColors()` — never hardcoded per component

---

## Developer Recommendations

1. Import all tokens from `../../theme/tokens` — never from any other file
2. Use the Typography component helpers (Heading, Title, Body, Caption, Overline, Mono) instead of raw Text elements
3. Use Button component for all tappable actions — never use TouchableOpacity with styled Text
4. Use Card and DarkCard as containers — never build a custom card container with manual styles
5. Use StatusBadge for all status indicators — never build a custom status chip
6. Use Avatar for all user/driver initials — never build a custom avatar

---

## Anti-Patterns

- `color: '#E8450F'` in a component file — use `Colors.primary`
- `padding: 16` — use `Spacing.base`
- `borderRadius: 24` — use `Radius['2xl']`
- `fontSize: 14` in a component — use `Typography.bodyMedium`
- `backgroundColor: '#1C1C2E'` — use `Colors.darkCard` or `Colors.navBg`
- Custom status badge with manual green/red colors — use `StatusBadge`
- Manually picking `#16A34A` for "completed" status — use `getStatusColors('Completed').color`
- Creating a new button with `TouchableOpacity` + `Text` — use the `Button` component
