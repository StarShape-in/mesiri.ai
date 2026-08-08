/**
 * MERCON Logistics Design System — React Native Tokens
 * All design decisions in one place. Never hardcode values in components.
 */

// ─── Brand Colors ────────────────────────────────────────────────────────────
export const Colors = {
  // Primary
  primary:        '#E8450F',
  primaryLight:   '#FFF0EB',
  primaryDark:    '#C7380A',

  /**
   * Drivers-feature accent. Slightly warmer than `primary`; the drivers
   * components (DriverActionButton/DriverRating/DriverStatusBadge) were
   * already built against this value — this token exists so it stops being
   * repeated as a literal. Do not swap it for `primary` without a design call.
   */
  accent:         '#F24822',
  accentLight:    '#FFF0EB',

  // Neutrals
  black:          '#111111',
  dark:           '#1A1A1A',
  darkCard:       '#1C1C2E',
  gray900:        '#111111',
  gray700:        '#3B3B44',
  gray500:        '#6E6E80',
  gray400:        '#9898A4',
  gray300:        '#D8D8DC',
  gray200:        '#EBEBED',
  gray100:        '#F5F5F7',
  gray50:         '#FAFAFA',
  white:          '#FFFFFF',

  // Semantic
  success:        '#16A34A',
  successLight:   '#F0FDF4',
  successBorder:  '#BBF7D0',
  warning:        '#D97706',
  warningLight:   '#FFFBEB',
  danger:         '#DC2626',
  dangerLight:    '#FEF2F2',
  info:           '#2563EB',
  infoLight:      '#EFF6FF',
  purple:         '#7C3AED',
  purpleLight:    '#F5F3FF',

  // Navigation
  navBg:          '#1C1C2E',

  // Status chips
  statusCompleted:   '#16A34A',
  statusCompletedBg: '#F0FDF4',
  statusTransit:     '#2563EB',
  statusTransitBg:   '#EFF6FF',
  statusDelayed:     '#D97706',
  statusDelayedBg:   '#FFFBEB',
  statusCancelled:   '#DC2626',
  statusCancelledBg: '#FEF2F2',
  statusPending:     '#6E6E80',
  statusPendingBg:   '#F5F5F7',

  // Aliases used by screens (kept for compatibility with the generated UI)
  gray800:        '#27272A',
  gray600:        '#52525B',
  error:          '#DC2626',
  errorLight:     '#FEF2F2',
} as const;

// ─── Spacing (8pt grid) ───────────────────────────────────────────────────────
export const Spacing = {
  xs:   4,
  sm:   8,
  md:   12,
  base: 16,
  lg:   20,
  xl:   24,
  '2xl': 32,
  '3xl': 40,
  '4xl': 48,
  '5xl': 64,
} as const;

// ─── Border Radius ────────────────────────────────────────────────────────────
export const Radius = {
  xs:   4,
  sm:   8,
  md:   12,
  lg:   16,
  xl:   20,
  '2xl': 24,
  '3xl': 32,
  full: 9999,
} as const;

// ─── Typography ───────────────────────────────────────────────────────────────
export const Typography = {
  // Display
  displayLarge:  { fontSize: 40, fontWeight: '800' as const, letterSpacing: -0.5, lineHeight: 48 },
  displayMedium: { fontSize: 32, fontWeight: '800' as const, letterSpacing: -0.5, lineHeight: 40 },
  displaySmall:  { fontSize: 28, fontWeight: '700' as const, lineHeight: 36 },

  // Headings
  headingXL:     { fontSize: 24, fontWeight: '700' as const, lineHeight: 32 },
  headingL:      { fontSize: 20, fontWeight: '700' as const, lineHeight: 28 },
  headingM:      { fontSize: 18, fontWeight: '600' as const, lineHeight: 26 },
  headingS:      { fontSize: 16, fontWeight: '600' as const, lineHeight: 24 },

  // Body
  bodyLarge:     { fontSize: 16, fontWeight: '400' as const, lineHeight: 26 },
  bodyMedium:    { fontSize: 14, fontWeight: '400' as const, lineHeight: 22 },
  bodySmall:     { fontSize: 13, fontWeight: '400' as const, lineHeight: 20 },

  // Labels
  caption:       { fontSize: 12, fontWeight: '400' as const, lineHeight: 18 },
  overline:      { fontSize: 11, fontWeight: '600' as const, letterSpacing: 1, lineHeight: 16 },

  // Buttons
  buttonLarge:   { fontSize: 16, fontWeight: '700' as const, lineHeight: 16 },
  buttonMedium:  { fontSize: 14, fontWeight: '600' as const, lineHeight: 14 },
  buttonSmall:   { fontSize: 12, fontWeight: '600' as const, lineHeight: 12 },

  // Mono (for IDs, codes)
  mono:          { fontSize: 12, fontFamily: 'monospace' as const, fontWeight: '600' as const },

  // Numeric font-size scale — screens use these as `fontSize: Typography.sm`
  xs:            12,
  sm:            14,
  md:            15,
  base:          16,
  lg:            18,
  xl:            20,
  '2xl':         24,
  '3xl':         28,
} as const;

// ─── Shadows ──────────────────────────────────────────────────────────────────
export const Shadows = {
  sm: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius: 3,
    elevation: 2,
  },
  md: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.08,
    shadowRadius: 12,
    elevation: 4,
  },
  lg: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.12,
    shadowRadius: 24,
    elevation: 8,
  },
  xl: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.16,
    shadowRadius: 32,
    elevation: 12,
  },
  primary: {
    shadowColor: '#E8450F',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.35,
    shadowRadius: 12,
    elevation: 6,
  },
  nav: {
    shadowColor: '#1C1C2E',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.45,
    shadowRadius: 24,
    elevation: 12,
  },
} as const;

// ─── Status helper ────────────────────────────────────────────────────────────
export type TripStatus = 'Completed' | 'In Transit' | 'Delayed' | 'Cancelled' | 'Pending';
export type VehicleStatus = 'Available' | 'On Trip' | 'Maintenance' | 'Inactive';
export type DocStatus = 'Active' | 'Expiring' | 'Expired' | 'Pending Upload';

export function getStatusColors(status: string) {
  const map: Record<string, { color: string; bg: string }> = {
    'Completed':     { color: Colors.statusCompleted,  bg: Colors.statusCompletedBg  },
    'In Transit':    { color: Colors.statusTransit,    bg: Colors.statusTransitBg    },
    'Delayed':       { color: Colors.statusDelayed,    bg: Colors.statusDelayedBg    },
    'Cancelled':     { color: Colors.statusCancelled,  bg: Colors.statusCancelledBg  },
    'Pending':       { color: Colors.statusPending,    bg: Colors.statusPendingBg    },
    'Available':     { color: Colors.statusCompleted,  bg: Colors.statusCompletedBg  },
    'On Trip':       { color: Colors.statusTransit,    bg: Colors.statusTransitBg    },
    'Maintenance':   { color: Colors.statusDelayed,    bg: Colors.statusDelayedBg    },
    'Inactive':      { color: Colors.statusPending,    bg: Colors.statusPendingBg    },
    'Active':        { color: Colors.statusCompleted,  bg: Colors.statusCompletedBg  },
    'Expiring':      { color: Colors.statusDelayed,    bg: Colors.statusDelayedBg    },
    'Expired':       { color: Colors.statusCancelled,  bg: Colors.statusCancelledBg  },
    'Paid':          { color: Colors.statusCompleted,  bg: Colors.statusCompletedBg  },
    'Draft':         { color: Colors.statusPending,    bg: Colors.statusPendingBg    },
    'Overdue':       { color: Colors.statusCancelled,  bg: Colors.statusCancelledBg  },
  };
  return map[status] ?? { color: Colors.statusPending, bg: Colors.statusPendingBg };
}
