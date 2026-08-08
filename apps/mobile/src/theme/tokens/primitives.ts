export const colors = {
  lime400: '#B7F52A',
  neutral0: '#FFFFFF',
  neutral50: '#F7F7F7',
  neutral100: '#F3F3F3',
  neutral200: '#E5E7EB', // Derived from users.tsx border
  neutral500: '#737373',
  neutral700: '#525252',
  neutral900: '#111111',
  
  // Status colors (defaults for later expansion)
  green500: '#22c55e',
  amber500: '#f59e0b',
  red500: '#ef4444',
  blue500: '#3b82f6',

  // Transparencies
  blackAlpha4: 'rgba(17, 17, 17, 0.04)',
  blackAlpha5: 'rgba(15, 15, 15, 0.05)',
  blackAlpha6: 'rgba(15, 15, 15, 0.06)',
  blackAlpha10: 'rgba(15, 15, 15, 0.10)',
  blackAlpha40: 'rgba(0,0,0,0.4)',
  blackAlpha50: 'rgba(0,0,0,0.5)',
  whiteAlpha10: 'rgba(255,255,255,0.10)',
  whiteAlpha60: 'rgba(255,255,255,0.60)',
};

export const spacing = {
  space1: 4,
  space2: 8,
  space3: 12,
  space4: 16,
  space5: 20,
  space6: 24,
  space8: 32,
  space10: 40,
};

export const typography = {
  familySans: 'System', // Replace with custom font if used
  sizeXs: 12,
  sizeSm: 14,
  sizeMd: 16,
  sizeLg: 18,
  sizeXl: 20,
  size2xl: 24,
  weightRegular: '400' as const,
  weightMedium: '500' as const,
  weightSemiBold: '600' as const,
  weightBold: '700' as const,
};

export const radii = {
  sm: 4,
  md: 8,
  lg: 12,
  xl: 24,
  full: 9999,
};

export const shadows = {
  none: {
    shadowColor: 'transparent',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0,
    shadowRadius: 0,
    elevation: 0,
  },
  subtle: {
    shadowColor: colors.neutral900,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
  },
  floating: {
    shadowColor: colors.neutral900,
    shadowOffset: { width: 0, height: -4 },
    shadowOpacity: 0.06,
    shadowRadius: 12,
    elevation: 8,
  },
  action: {
    shadowColor: colors.neutral900,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 8,
    elevation: 6,
  },
};

export const zIndex = {
  base: 1,
  stickyHeader: 10,
  stickyScope: 20,
  bottomNavigation: 30,
  overlay: 40,
  modal: 50,
  toast: 60,
};

export const primitives = {
  colors,
  spacing,
  typography,
  radii,
  shadows,
  zIndex,
};
