# MERCON Animation and Motion Specification

## Motion Principles

1. **Purpose over decoration.** Every animation must communicate something: state change, hierarchy, causality. Never add animation for visual richness alone.
2. **Fast and responsive.** Interactions respond within 100ms. Transitions complete within 300ms for screen-level changes, 200ms for element-level changes.
3. **Ease-out is the default.** Elements entering the screen decelerate into position. Ease-in is used only for exit animations.
4. **Honor accessibility.** Respect `AccessibilityInfo.isReduceMotionEnabled`. When reduced motion is enabled, replace all position/scale animations with opacity fades.
5. **No janky animations.** All animations must run at 60fps. Never animate layout properties (width, height, padding, margin) — use `transform` instead.

---

## Duration Scale

| Name | Duration | Use Case |
|------|---------|---------|
| instant | 0ms | State swaps with no visual transition (text changes, badge label updates) |
| micro | 150ms | Press feedback, toggle, small icon state change |
| fast | 200ms | Input focus ring, badge color cross-fade, dropdown item |
| standard | 300ms | Page transitions, modal entry, bottom sheet, drawer |
| slow | 400ms | Complex entry sequences, hero elements |

**Default:** 200ms for component-level, 300ms for screen-level.

---

## Easing Curves

| Curve | CSS Equivalent | React Native | Use Case |
|-------|---------------|-------------|---------|
| ease-out | `cubic-bezier(0, 0, 0.2, 1)` | `Easing.out(Easing.ease)` | Elements entering view, default |
| ease-in | `cubic-bezier(0.4, 0, 1, 1)` | `Easing.in(Easing.ease)` | Elements exiting view |
| ease-in-out | `cubic-bezier(0.4, 0, 0.2, 1)` | `Easing.inOut(Easing.ease)` | State transitions, toggles |
| spring | spring(damping: 15, stiffness: 150) | `Animated.spring` | Bounce elements, FAB, success states |

---

## Button Interactions

### Press Feedback

**Mechanism:** `TouchableOpacity` `activeOpacity` property.

| Variant | activeOpacity |
|---------|--------------|
| primary, danger, success | 0.82 |
| secondary, outline, ghost | 0.75 |
| Navigation tabs | 0.70 |
| FAB | 0.85 |
| Card rows | 0.80 |

**Additional press animation (optional, for primary CTA only):**
- `transform: [{ scale: 0.96 }]` on press-in
- `transform: [{ scale: 1.0 }]` on press-out
- Duration: 150ms ease-out
- Implementation: `Animated.timing` inside `onPressIn` / `onPressOut`

### Loading State

- Replace label text with ActivityIndicator
- No size change on loading — avoid layout shift
- ActivityIndicator color: `Colors.white` for primary/danger/success, `Colors.primary` for other variants
- Spinner appears on the same tick the loading state is set (no animation needed)

---

## Input Interactions

### Focus Ring

When an Input transitions from `default` to `focused`:
- `borderColor` animates from `transparent` to `rgba(232, 69, 15, 0.25)` (primary at 25% opacity)
- Duration: 200ms ease-out
- Implementation: `Animated.timing` on a border color interpolation

### State Transitions (error / success)

When state changes from `default` to `error`:
- Background color: `#F5F5F7` → `#FEF2F2` (danger light)
- Border color: `transparent` → `rgba(220, 38, 38, 0.25)` (danger at 25%)
- Error text fades in below: `opacity: 0 → 1`, 150ms ease-out

When state changes from `error` to `success`:
- Background: `#FEF2F2` → `#F0FDF4` (success light)
- Border: `rgba(220,38,38,0.25)` → `rgba(22,163,74,0.25)` (success at 25%)
- Duration: 200ms ease-in-out

---

## Badge / Status Badge Interactions

### Status Color Change

When a trip or vehicle status changes (e.g., Pending → In Transit):
- New badge fades in with `opacity: 0 → 1` over 200ms ease-out
- Old badge fades out simultaneously
- No position movement

### FilterChip Toggle

When a FilterChip activates:
- Background: `Colors.gray100 → Colors.primary`
- Text color: `Colors.dark → Colors.white`
- Duration: 150ms ease-out

---

## Navigation Transitions (React Navigation)

### DriverBottomNav — Tab Switch

- Default React Navigation bottom tabs: horizontal slide (tab to the right slides in from right)
- Customize to cross-fade for a cleaner experience:
  - `animation: 'fade'` in `screenOptions`
  - Duration: 200ms

### Stack Navigator — Screen Push

- New screen slides in from right: `translateX: screenWidth → 0`
- Previous screen shifts left: `translateX: 0 → -screenWidth * 0.3`
- Duration: 300ms ease-out
- Back gesture: swipe right from left edge

### Modal Screens (CreateTrip, image pickers)

- Sheet slides up from bottom: `translateY: screenHeight → 0`
- Backdrop fades in: `opacity: 0 → 0.5`
- Duration: 300ms ease-out
- Dismiss: tap backdrop or swipe down

---

## Bottom Sheet Behavior

Used for: filter drawers, driver selection, vehicle selection in Create Trip.

- **Entry:** `translateY: sheetHeight → 0`, 300ms ease-out
- **Exit:** `translateY: 0 → sheetHeight`, 250ms ease-in
- **Backdrop:** `opacity: 0 → 0.4` (black), 250ms ease-out
- **Drag to dismiss:** threshold at 40% of sheet height downward drag
- **Snap points:** 50% and 90% of screen height

---

## Page Transitions (Specific Screens)

### Splash → Login

- Splash logo scale-down and fade: `scale: 1 → 0.8`, `opacity: 1 → 0`, 300ms ease-in
- Login screen fades in: `opacity: 0 → 1`, 300ms ease-out, 100ms delay

### OTP Success → HomeScreen

- Full screen white flash overlay: `opacity: 0 → 1 → 0` over 600ms total
- HomeScreen slides in underneath from bottom

### Trip Completed Screen Entry

- Green circle animates in: `scale: 0 → 1` with spring (damping: 12, stiffness: 100)
- Checkmark draws in (stroke dashoffset animation) or bounces in
- Stats text fade-in sequentially: each stat delayed by 100ms from previous

---

## Micro-Interactions

### Progress Bar Fill

- Trip progress bars animate on mount: `width: 0% → actual%`
- Duration: 600ms ease-out
- Used in: ActiveTrip, HomeScreen trip cards, TripDetails

### Online Status Dot (Active Trip / Driver)

- Active/on-trip dot has a pulsing ring animation:
  - Scale ring from 1 → 1.5, opacity 1 → 0
  - Loop: 2000ms repeat
  - Color: `Colors.success` ring for available drivers

### Notification Badge

- Badge count increment: scale bounce — `scale: 1 → 1.3 → 1`, 200ms spring
- New badge appears: `opacity: 0 → 1`, 150ms ease-out

### KPI Number Update

- When a KPI value updates on the dashboard, animate with counter:
  - Animate displayed number from previous value to new value
  - Duration: 800ms ease-out
  - Implement with `Animated.timing` + `interpolate` on a 0→1 animation value

### Card Row Press

- `activeOpacity: 0.8` on TouchableOpacity wrapping card row
- No additional animation needed — the opacity feedback is sufficient

---

## Avatar Group Animation

When new avatars are added to an AvatarGroup (e.g., multiple drivers on a trip):
- New avatar slides in from the right and pushes others left
- Duration: 250ms ease-out
- Overflow "+N" badge updates with scale bounce

---

## Loading States

### Skeleton Screens

Not a specific animation component — implement as:
- Gray rectangle placeholders in the shape of content (`Colors.gray200`, `Radius.md`)
- Animated shimmer: a gradient that travels left to right
  - Gradient: `Colors.gray200 → Colors.gray100 → Colors.gray200`
  - Duration: 1200ms loop, ease-in-out

### Spinner (ActivityIndicator)

- Used inside Button (loading state)
- Also used on full-screen loading overlays (e.g., after OTP submit)
- Color: `Colors.primary` on white backgrounds, `Colors.white` on dark/primary backgrounds

---

## Reduced Motion Handling

When `AccessibilityInfo.isReduceMotionEnabled()` returns `true`:

- Replace all `transform` animations with `opacity` animations
- Remove spring animations — use `opacity: 0 → 1` instead
- Remove progress bar fill animation — show final state immediately
- Remove counter animations — show final number immediately
- Keep: loading spinners (they communicate ongoing state, not decoration)
- Keep: status transitions (they communicate important information)

---

## Implementation Notes

- Use `Animated` API for most component-level animations (React Native core)
- Use `react-native-reanimated` for gesture-based animations (swipe to dismiss, drag)
- Never use `LayoutAnimation` — it affects all layout changes globally
- All durations are specified in milliseconds
- Always use `useNativeDriver: true` where possible (opacity, transform)
- `backgroundColor` transitions cannot use native driver — keep them to a minimum

---

## Animation Checklist

Before marking a screen implementation complete, verify:
- [ ] All TouchableOpacity elements have correct activeOpacity values
- [ ] Primary buttons have press scale feedback (optional but recommended)
- [ ] Input focus transitions are smooth (200ms)
- [ ] Status badge colors do not flash abruptly on filter change
- [ ] Progress bars animate on mount (600ms ease-out)
- [ ] Page transitions match the navigation type (push vs modal)
- [ ] Skeleton screens have shimmer effect
- [ ] Reduced motion preference is respected
