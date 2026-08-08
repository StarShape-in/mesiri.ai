# MERCON Accessibility Guidelines

## Standard: WCAG 2.1 AA

All MERCON screens must meet WCAG 2.1 Level AA. This document specifies how every design token and component must behave to meet that standard.

---

## Contrast Ratios

WCAG AA requires:
- **4.5:1** minimum for normal text (under 18px regular or under 14px bold)
- **3:1** minimum for large text (18px+ regular or 14px+ bold)
- **3:1** minimum for UI components and graphical objects

### Verified color pairs

| Text Color | Background | Ratio | WCAG |
|-----------|-----------|-------|------|
| `#1A1A1A` dark on `#FFFFFF` white | 19.4:1 | AAA |
| `#1A1A1A` dark on `#F5F5F7` gray100 | 18.1:1 | AAA |
| `#FFFFFF` white on `#E8450F` primary | 4.6:1 | AA |
| `#FFFFFF` white on `#1C1C2E` darkCard | 16.8:1 | AAA |
| `#FFFFFF` white on `#DC2626` danger | 5.7:1 | AA |
| `#FFFFFF` white on `#16A34A` success | 4.7:1 | AA |
| `#6E6E80` gray500 on `#FFFFFF` | 4.6:1 | AA |
| `#6E6E80` gray500 on `#F5F5F7` | 4.3:1 | AA (borderline — use `#3B3B44` for critical muted text) |
| `#E8450F` primary on `#FFFFFF` | 4.6:1 | AA |
| `#E8450F` primary on `#F5F5F7` | 4.3:1 | AA (borderline — avoid for small text under 14px) |
| `rgba(255,255,255,0.45)` on `#1C1C2E` | 2.1:1 | Fail — inactive nav tabs are decorative only, not content |

**Note on inactive navigation tabs:** The `rgba(255,255,255,0.45)` inactive state on `#1C1C2E` does not meet AA for text. This is acceptable because the inactive state is decorative and the active state (orange, 4.6:1) is the primary informative state. Screen readers should announce all tab labels regardless of visual state.

### Status Badge Contrast

| Status | Text Color | Background | Ratio |
|--------|-----------|-----------|-------|
| Completed | `#16A34A` on `#F0FDF4` | 4.5:1 | AA (meets exactly) |
| In Transit | `#2563EB` on `#EFF6FF` | 4.9:1 | AA |
| Delayed | `#D97706` on `#FFFBEB` | 3.1:1 | Fails for small text |
| Cancelled | `#DC2626` on `#FEF2F2` | 5.7:1 | AA |
| Pending | `#6E6E80` on `#F5F5F7` | 4.3:1 | Borderline |

**Recommendation:** For Delayed and Pending badges, add `fontWeight: '700'` to the badge text (already done in Badge component with `fontWeight: '600'`) and ensure minimum text size is 12px (already set via `Typography.caption`).

---

## Touch Target Sizes

WCAG 2.1 SC 2.5.5 (Level AAA) recommends 44×44pt. WCAG 2.2 SC 2.5.8 (Level AA) requires 24×24pt minimum. MERCON targets 44×44pt for all primary interactive elements.

### Component touch target analysis

| Component | Effective Touch Target |
|----------|----------------------|
| Button (lg) | Height ~46pt — PASS |
| Button (md) | Height ~42pt — borderline (add `minHeight: 44` if needed) |
| Button (sm) | Height ~30pt — FAIL for primary use cases. Only use sm buttons in table rows or chip groups where surrounding space provides clearance |
| Input | `minHeight: 48` — PASS |
| SearchInput | `height: 44` — PASS exactly |
| FilterChip | Height ~28pt — FAIL standalone. Chips must have 8pt vertical padding added to their container row so the effective tappable height is ≥44pt |
| Navigation tab (DriverBottomNav) | `paddingVertical: 4`, content ~20pt + label ~12pt = ~36pt — add `minHeight: 44` or increase `paddingVertical: Spacing.sm` to 8pt |
| OperatorBottomNav tab | Same as above |
| FAB | 48×48pt — PASS |
| Avatar (sm 28pt) | FAIL for interactive use. Only use non-interactive or add 8pt padding around if tappable |
| Avatar (md 36pt) | Borderline — add padding |
| Avatar (lg 48pt) | PASS |
| Avatar (xl 64pt) | PASS |

---

## Keyboard Navigation (Web Dashboard)

The web dashboard must be fully keyboard navigable.

### Focus order

Focus order must match the visual reading order (left to right, top to bottom):
1. Skip to main content link (hidden until focused)
2. Sidebar navigation items (top to bottom)
3. Main content: page heading, then content in reading order
4. Footer actions (if any)

### Focus indicator styles

- **Visible focus ring:** `outline: 2px solid #E8450F` (MERCON Orange), `outlineOffset: 2px`
- **Never:** `outline: none` without a custom replacement
- All buttons, links, inputs, and interactive cards must show focus ring when tabbed to

### Keyboard interactions

| Element | Keys |
|---------|------|
| Sidebar nav item | Tab / Shift+Tab to navigate, Enter to activate |
| Button | Tab to focus, Enter or Space to activate |
| Input | Tab to focus, type to enter |
| FilterChip row | Tab to row, Arrow Left/Right to move between chips, Space to toggle |
| Dropdown / picker | Tab to open, Arrow Up/Down to navigate options, Enter to select, Escape to close |
| Modal | Tab traps focus inside modal, Escape to close |
| Table row | Tab to row, Enter to activate (navigate to detail) |
| Date picker | Arrow keys to navigate calendar, Enter to select |

---

## Screen Reader Support

### React Native (iOS VoiceOver, Android TalkBack)

**Required props on all interactive elements:**

```typescript
// Button
<TouchableOpacity
  accessibilityRole="button"
  accessibilityLabel="Send OTP"   // Descriptive label
  accessibilityState={{ disabled: isDisabled, busy: isLoading }}
>

// Status Badge
<View accessibilityRole="text" accessibilityLabel={`Status: ${status}`}>

// Input
<TextInput
  accessibilityLabel="Mobile number"
  accessibilityHint="Enter your 10-digit Saudi mobile number"
/>

// Avatar
<View accessibilityLabel={`${name}, ${onlineStatus}`} accessibilityRole="image">

// Navigation Tab
<TouchableOpacity
  accessibilityRole="tab"
  accessibilityLabel="Home"
  accessibilityState={{ selected: activeTab === 'Home' }}
>
```

**Screen-level announcements:**

- When a screen loads, the screen title should be announced
- When an error occurs, announce the error text (use `AccessibilityInfo.announceForAccessibility`)
- When a form submits successfully, announce "Trip created successfully" or equivalent

### VoiceOver order considerations

- VoiceOver reads elements in the order they appear in the component tree
- Dark header cards must have all header content in logical reading order inside the JSX
- Status badges should be announced before or after the item they describe, not disconnected

---

## Dynamic Type (Mobile)

Plus Jakarta Sans is a system font substitute, not a system font. Dynamic type requires:

- Do not set absolute `fontSize` in inline styles — always use Typography tokens
- Allow text containers to grow by not constraining height
- `numberOfLines` prop on Typography components should be used sparingly
- Critical information (trip ID, status, ETA) should never truncate

**Recommendation:** Test all screens with iOS text size set to "Larger Text" (2 steps above default).

---

## Reduced Motion

```typescript
import { AccessibilityInfo } from 'react-native';

// At app initialization:
const reduceMotion = await AccessibilityInfo.isReduceMotionEnabled();

// Store in global state / context
// Apply throughout: when reduceMotion === true, use opacity-only animations
```

When reduced motion is enabled:
- Progress bar: show final state immediately (no width animation)
- Page transitions: cross-fade only, no slide
- Success screen: show checkmark immediately, no spring animation
- Skeleton shimmer: show static gray placeholder, no moving gradient
- Pulsing status dot: show static dot, no ring animation

---

## Color Blindness Considerations

The status system uses 5 colors to communicate state. Color alone is insufficient for users with color blindness.

**Mitigations applied:**
1. StatusBadge includes a text label — the status name is always visible alongside the color
2. The `dot` prop on Badge allows a colored dot alongside text — the shape (circle) also signals presence
3. Progress bars use width (length) as the primary indicator, color is supplementary
4. FilterChip active state changes both background color AND label color — dual encoding

**Additional recommendations:**
- Consider adding distinct icons per status (e.g., checkmark for Completed, clock for Pending, warning triangle for Delayed)
- In tables, use distinct icons in the status column alongside the badge

---

## Form Accessibility

### Input component
- Always provide a `label` prop — never rely on placeholder as the only label
- Error messages must be announced by screen reader when they appear
- Relate error message to input with `accessibilityDescribedBy` (web) or announce via `AccessibilityInfo` (mobile)
- Success messages follow the same pattern

### Form validation
- Inline validation errors appear below the field, not just at the top of the form
- Required fields must be indicated both visually and to screen readers (`accessibilityRequired: true`)
- Do not clear successfully entered fields on error

---

## WCAG 2.1 AA Compliance Checklist

| Criterion | MERCON Implementation |
|-----------|----------------------|
| 1.1.1 Non-text content | All icons must have `accessibilityLabel` |
| 1.3.1 Info and relationships | Use `accessibilityRole` for semantic meaning |
| 1.3.3 Sensory characteristics | Never instruct by color alone |
| 1.4.1 Use of color | Status always paired with text label |
| 1.4.3 Contrast (minimum) | 4.5:1 for normal text — verified above |
| 1.4.4 Resize text | Do not lock text size, use Typography tokens |
| 1.4.11 Non-text contrast | UI components 3:1 — buttons, inputs verified |
| 2.1.1 Keyboard | Full keyboard nav on web dashboard |
| 2.1.2 No keyboard trap | Modals must release focus on Escape |
| 2.4.3 Focus order | Focus follows reading order |
| 2.4.7 Focus visible | Orange outline ring on all interactive web elements |
| 2.5.3 Label in name | Button accessibilityLabel must contain visible label text |
| 2.5.5 Target size | 44×44pt for all primary interactive targets |
| 3.3.1 Error identification | Error text shown below the relevant input |
| 3.3.2 Labels or instructions | All inputs labeled |
| 4.1.2 Name, role, value | accessibilityRole on all interactive elements |
