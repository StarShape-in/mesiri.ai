# MERCON Design QA Checklist

Use this checklist for every screen before marking it implementation-complete. Check every item — partial completion does not pass.

---

## Spacing

- [ ] Screen horizontal edge padding is exactly `Spacing.base` (16px) or greater on both sides
- [ ] No element touches the screen edge without padding
- [ ] Vertical spacing between sections uses values from the Spacing scale (4, 8, 12, 16, 20, 24, 32, 40, 48, 64)
- [ ] No `margin` or `padding` values that are odd numbers (3, 5, 7, 9, 11, 13, 15, etc.) unless intentionally micro-adjusted (e.g., `Spacing.xs + 2 = 6`)
- [ ] Gap between icon and text in buttons is `Spacing.sm` (8px)
- [ ] Gap between icon and text in nav tabs is 2px
- [ ] Card internal content has explicit padding (not from the Card component itself)
- [ ] Bottom safe area is respected — content does not go behind the navigation pill or home indicator
- [ ] ScrollView contentContainerStyle adds `paddingBottom` to prevent content hiding behind nav

---

## Colors

- [ ] No hex color literals in component files — all colors reference `Colors.*` tokens
- [ ] Primary orange (`#E8450F`) only appears on: primary buttons, active nav tabs, FAB border, FAB icon, FilterChip active, progress bar fill, input focus border, brand text
- [ ] Dark navy (`#1C1C2E`) only appears on: navigation pill, DarkCard, dark header sections
- [ ] Page background is `Colors.gray100` (`#F5F5F7`) — not white, not gray50
- [ ] Card backgrounds are `Colors.white` (`#FFFFFF`)
- [ ] All status colors resolve via `getStatusColors()` — no manually assigned status colors
- [ ] Disabled elements use `opacity: 0.45` — no manual gray color for disabled state
- [ ] Inactive nav tab icons/labels use `rgba(255,255,255,0.45)` — not a gray from the palette

---

## Typography

- [ ] Every text element uses a Typography token — no `fontSize` or `fontWeight` literals in component code
- [ ] Typography components (Heading, Title, Body, Caption, Overline, Mono) are used for all text
- [ ] Trip IDs, driver IDs, vehicle IDs, invoice numbers use `Mono` component (monospace, brand color)
- [ ] Section labels above lists use `Overline` (uppercase, tracked, muted)
- [ ] Button labels use `Typography.buttonLarge/Medium/Small` via the Button component — not raw Text
- [ ] No `fontSize` above 40 unless it is `Typography.displayLarge`
- [ ] No `fontWeight` values other than: 400, 600, 700, 800
- [ ] `headingL` (20px/700) is used for screen hero headings
- [ ] `headingS` (16px/600) is used for card section titles
- [ ] `bodyMedium` (14px/400) is the default body text
- [ ] `caption` (12px/400) is used for timestamps, secondary metadata, helper text

---

## Icons

- [ ] All icons are from `lucide-react-native` — no emoji, no other libraries
- [ ] Navigation tab icons are the correct size: 20px for Driver, 18px for Operator
- [ ] Input prefix/suffix icons are 16px
- [ ] Button icons are 16px (sm/md) or 18px (lg)
- [ ] Icon color matches the context: active state = `Colors.primary`, inactive = muted or as per variant
- [ ] The FAB uses the `Plus` lucide icon at 22px, color `Colors.primary`
- [ ] No decorative icons — every icon communicates something
- [ ] Icons have `accessibilityElementsHidden={true}` if purely decorative, or `accessibilityLabel` if informative

---

## Component Integrity

- [ ] All buttons use the `Button` component — no custom TouchableOpacity with styled Text
- [ ] All status indicators use `StatusBadge` component — no manually colored badges
- [ ] All text inputs use the `Input` component — no raw `TextInput` in screens
- [ ] All search bars use `SearchInput` component
- [ ] All user/driver initials use the `Avatar` component
- [ ] All content containers use `Card` or `DarkCard` — no custom card styles
- [ ] All filter rows use `FilterChip` components
- [ ] All typographic text uses Typography helper components (Heading, Title, Body, Caption, Overline, Mono)

---

## Animations and Interactions

- [ ] All `TouchableOpacity` elements have the correct `activeOpacity`:
  - Primary/danger/success buttons: 0.82
  - Secondary/outline/ghost buttons: 0.75
  - Navigation tabs: 0.70
  - FAB: 0.85
  - Card rows: 0.80
- [ ] Input focus ring animates on focus (200ms ease-out, orange at 25% opacity)
- [ ] Progress bars animate on mount (600ms ease-out, width from 0% to actual%)
- [ ] Loading states show spinner (ActivityIndicator), not a static label
- [ ] Button loading state hides the label text completely while spinner is visible
- [ ] Page transitions match the navigator type (push = slide right, modal = slide up)
- [ ] Reduced motion: `AccessibilityInfo.isReduceMotionEnabled` is checked, animations replaced with opacity fades

---

## Navigation

- [ ] Every screen has a visible way to go back (back button or nav tab)
- [ ] TripCompleted screen has `gestureEnabled: false` — back swipe disabled
- [ ] Login and Splash screens have `gestureEnabled: false`
- [ ] Modal screens (CreateTrip, AddDriver, CreateInvoice) slide up and can be dismissed by swipe down or back button
- [ ] Navigation tabs show the correct active tab for the current screen
- [ ] FAB navigates to CreateTripScreen as a modal

---

## States — All screens must handle:

- [ ] **Loading:** Skeleton placeholders or ActivityIndicator shown while data fetches
- [ ] **Empty:** Meaningful empty state with illustration and action (if applicable)
- [ ] **Error:** Error message with retry option
- [ ] **Success:** Confirmation shown after successful actions
- [ ] **Offline:** Offline banner shown, forms disabled, cached data displayed with stale indicator
- [ ] **Disabled:** Interactive elements at opacity 0.45, not hidden

---

## Form Screens — Additional checks:

- [ ] Required fields are indicated (asterisk or label annotation)
- [ ] Submit button is disabled until all required fields are filled
- [ ] Error messages appear below the specific field that failed, not only at the top
- [ ] Success feedback is shown after submission (toast or navigation to confirmation screen)
- [ ] Keyboard does not cover the focused input (KeyboardAvoidingView applied)
- [ ] `returnKeyType` set appropriately (`next` for fields with more fields below, `done` for last field)
- [ ] Multiline inputs scroll internally, do not cause the entire screen to scroll unexpectedly

---

## Accessibility

- [ ] All buttons have `accessibilityRole="button"` and `accessibilityLabel` matching visible label
- [ ] All navigation tabs have `accessibilityRole="tab"` and `accessibilityState={{ selected }}`
- [ ] All inputs have `accessibilityLabel` and `accessibilityHint`
- [ ] All StatusBadge elements have `accessibilityLabel="Status: {status}"`
- [ ] Touch targets are minimum 44×44pt for all primary actions
- [ ] No interactive elements rely on color alone to convey state (all paired with text or icon)
- [ ] Screen titles are announced when screen loads
- [ ] Dynamic errors are announced via `AccessibilityInfo.announceForAccessibility`

---

## Responsive / Cross-Device

- [ ] Screen renders correctly on iPhone SE (375pt width) — no overflow, no clipped content
- [ ] Screen renders correctly on iPhone 14 Pro Max (430pt width) — no excessive whitespace
- [ ] Tested on Android (Pixel 5 at 393pt width)
- [ ] StatusBar style matches the screen header: `light-content` for dark headers, `dark-content` for light
- [ ] SafeAreaView wraps every screen root
- [ ] Bottom content does not sit behind the navigation pill or Android nav bar

---

## Pixel-Perfect Verification

- [ ] Compare the implemented screen to the design reference side-by-side
- [ ] Border radius on cards is exactly 24px (Radius['2xl']) — not more, not less
- [ ] Border radius on buttons is exactly 20px (Radius.xl)
- [ ] Border radius on badges and chips is `full` (9999) — fully circular ends
- [ ] Navigation pill background is exactly `#1C1C2E` — not a lighter or darker shade
- [ ] Active tab color is exactly `#E8450F` — not coral, not tomato, not any approximation
- [ ] Card border is exactly `rgba(0,0,0,0.07)` — very subtle, barely visible

---

## Final Sign-Off

Before marking any screen as "Done", confirm:

- [ ] All items above are checked
- [ ] Tested on both iOS and Android simulators
- [ ] VoiceOver / TalkBack tested for at least the primary user flow on this screen
- [ ] No TypeScript errors in the file
- [ ] No console warnings related to this screen
- [ ] All TODO comments replaced with actual implementations (specifically: icon placeholders)
