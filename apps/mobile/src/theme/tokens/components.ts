import { SemanticColors } from './semantic';

export interface ComponentColors {
  // Navigation
  topbarBackground: string;
  topbarBorder: string;
  
  bottomNavBackground: string;
  bottomNavActiveIconFill: string;
  bottomNavActiveIconStroke: string;
  bottomNavInactiveIconFill: string;
  bottomNavInactiveIconStroke: string;

  // AI Button
  aiButtonBackground: string;
  aiButtonForeground: string;
  aiButtonBorder: string;
  aiButtonShadow: string;

  // Scope Controls
  scopeControlBackground: string;
  scopeControlActiveBackground: string;
  scopeControlActiveForeground: string;
  scopeControlBorder: string;
  scopeControlChevron: string;
  scopeSheetOverlay: string;

  // Profile
  profileAvatarOutline: string;

  // Rare Dark Surfaces (e.g. Portfolio Snapshot)
  rareSurfaceBackground: string;
  rareSurfaceForeground: string;
  rareSurfaceTextSecondary: string;
  rareSurfaceBorder: string;
  rareSurfaceAccent: string;

  // Cards
  projectCardBackground: string;
  projectCardBorder: string;
}

export const createComponentColors = (semantic: SemanticColors): ComponentColors => ({
  topbarBackground: semantic.backgroundSurface,
  topbarBorder: semantic.borderSubtle,

  bottomNavBackground: semantic.backgroundSurface,
  bottomNavActiveIconFill: semantic.actionPrimary,
  bottomNavActiveIconStroke: semantic.borderStrong,
  bottomNavInactiveIconFill: 'transparent',
  bottomNavInactiveIconStroke: semantic.textMuted,

  aiButtonBackground: semantic.actionPrimary,
  aiButtonForeground: semantic.actionPrimaryForeground,
  aiButtonBorder: semantic.borderStrong,
  aiButtonShadow: semantic.borderStrong, // Used for shadowColor

  scopeControlBackground: semantic.backgroundSurface,
  scopeControlActiveBackground: semantic.actionPrimary,
  scopeControlActiveForeground: semantic.actionPrimaryForeground,
  scopeControlBorder: semantic.borderStrong,
  scopeControlChevron: semantic.textPrimary,
  scopeSheetOverlay: 'rgba(0,0,0,0.4)', // Alternatively map to a new semantic token

  profileAvatarOutline: semantic.borderStrong,

  rareSurfaceBackground: semantic.backgroundInverse,
  rareSurfaceForeground: semantic.textInverse,
  rareSurfaceTextSecondary: 'rgba(255,255,255,0.60)',
  rareSurfaceBorder: 'rgba(255,255,255,0.10)',
  rareSurfaceAccent: semantic.actionPrimary,

  projectCardBackground: semantic.backgroundSurface,
  projectCardBorder: semantic.borderDefault,
});
