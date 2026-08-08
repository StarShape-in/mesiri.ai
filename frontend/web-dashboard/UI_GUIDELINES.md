# MERCON Web Dashboard - UI & Design Guidelines

This document serves as the single source of truth for frontend UI development. Any new pages, components, or features must adhere to these rules to ensure the dashboard remains clean, modern, and visually consistent.

---

## 1. Color Palette Rules

**Never use default browser colors or generic Tailwind colors without checking this list first.**

*   **Primary Brand Color**: `#E8450F` (Orange). Used for primary buttons, active states, key icons, and primary chart elements.
*   **Global Background**: `#F5F5F7`. Every protected page uses this as the base canvas. Never use pure white `#FFFFFF` for the page background.
*   **Card Backgrounds**: Pure White `#FFFFFF` for standard cards. Dark `#1C1C2E` for emphasized/hero cards (like the Route Overview on Trip Details).
*   **Text Colors**:
    *   **Primary**: `#111111` (Near black). Used for all headers, titles, and primary data points.
    *   **Secondary**: `#6E6E80`. Used for subtitles, descriptions, and secondary data.
    *   **Tertiary / Muted**: `#9898A4`. Used for placeholders, table headers, and disabled states.
*   **Semantic Colors**:
    *   **Success**: `#16A34A` (Green)
    *   **Warning**: `#D97706` or `#CA8A04` (Yellow/Amber)
    *   **Error**: `#DC2626` (Red)
    *   **Info**: `#2563EB` (Blue)
    *   *Rule: When using semantic colors for backgrounds (like in badges or alert boxes), always use a 10% or 15% opacity tint of the base color (e.g., `#F0FDF4` for green backgrounds).*

---

## 2. Typography Rules

*   **Font Family**: The dashboard uses a modern Sans-Serif font (Inter / Plus Jakarta Sans).
*   **Headers & Numbers**: Must use `font-bold`. We do not use semi-bold for primary titles or large KPI numbers.
*   **Labels & Table Headers**: Must be styled as `text-[10px] font-bold uppercase tracking-wider text-[#9898A4]`. This specific style is critical for the "technical" look of the logistics dashboard.
*   **Body Text**: Standard body text is `text-xs` or `text-sm`. We rarely use `text-base` except for very specific highlighted data points.

---

## 3. Borders, Shadows, and Radii (The Shape Language)

**This is the most critical rule for maintaining the "Premium" feel. Do not use sharp corners or heavy drop shadows.**

*   **Border Radius (Corners)**:
    *   **Large Cards / Page Modals**: `rounded-[24px]` or `rounded-2xl`.
    *   **Buttons, Inputs, Small Containers**: `rounded-xl` (12px).
    *   **Badges**: Heavily rounded or `rounded-md` depending on context, but never sharp.
*   **Borders**:
    *   Do not use thick borders or solid gray borders like `border-gray-300`.
    *   Use translucent black for subtle depth: `border border-black/[0.04]` to `border-black/[0.08]`.
    *   For dark cards, use `border-white/5` or `border-white/10`.
*   **Shadows**:
    *   Use `shadow-sm` for standard cards.
    *   Never use `shadow-lg` or `shadow-xl` unless it is a floating modal or dropdown menu. The UI relies on borders and background contrast, not heavy shadows.

---

## 4. Layout & Spacing Rules

*   **Page Padding**: The main scrollable content area must always have `px-6 pb-6` (24px padding on X-axis and Bottom).
*   **Grid Gaps**: When creating grids for cards or forms, use `gap-4` or `gap-5`.
*   **Card Padding**: Standard internal padding for a card is `p-5` or `p-6`.
*   **Flexbox over Floats**: Always use flexbox or CSS Grid for alignment.

---

## 5. Component Usage Rules

**Do not reinvent the wheel. If a component exists in `@/components/ui/`, you MUST use it.**

*   **Page Wrapper**: Every protected page must be wrapped in `<DashboardLayout>`.
*   **Buttons**: Always use the `<Btn>` component. Never write a raw `<button>` tag unless it's a completely custom icon toggle.
*   **Forms**: Always use `<FormInput>` and wrap logical groups in `<FormSection>`.
*   **Tables**: Always use `<DataTable>`. Do not build raw HTML tables unless it is a highly specific, one-off visualization (like the 5-row recent trips on the dashboard).
*   **Status Indicators**: Always use `<StatusBadge status={...} />`. Do not create custom spans for statuses.

---

## 6. Icons & Imagery

*   **Icon Library**: Strictly use `lucide-react`. Do not mix in FontAwesome, HeroIcons, or custom SVGs unless explicitly required for a highly specific logo or map marker.
*   **Icon Sizing**: 
    *   Buttons: `size={13}` or `size={14}`
    *   Sidebar: `size={16}`
    *   KPI Cards: `size={20}` or `size={24}`

---

## 7. Animations & Interactions

*   **Page Load**: The main content wrapper of every page should include the `animate-fade-in` class.
*   **Hover States**: 
    *   All clickable elements must have a hover state.
    *   Buttons generally use `hover:scale-[1.02]` or a slight background color shift.
    *   Table rows must use `hover:bg-[#FAFAFA] cursor-pointer transition-colors`.
*   **Transitions**: Apply `transition-all duration-150` or `transition-colors` to inputs, buttons, and links to ensure nothing feels "snappy" or rigid.
