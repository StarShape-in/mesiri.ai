import { primitives } from './primitives';

export interface SemanticColors {
  backgroundApp: string;
  backgroundSurface: string;
  backgroundSubtle: string;
  backgroundInverse: string;

  textPrimary: string;
  textSecondary: string;
  textMuted: string;
  textInverse: string;

  borderSubtle: string;
  borderDefault: string;
  borderStrong: string;

  actionPrimary: string;
  actionPrimaryForeground: string;

  actionSecondary: string;

  focusRing: string;

  statusSuccess: string;
  statusSuccessBackground: string;
  statusSuccessBorder: string;
  statusSuccessForeground: string;

  statusWarning: string;
  statusWarningBackground: string;
  statusWarningBorder: string;
  statusWarningForeground: string;

  statusDanger: string;
  statusDangerBackground: string;
  statusDangerBorder: string;
  statusDangerForeground: string;

  statusInfo: string;
  statusInfoBackground: string;
  statusInfoBorder: string;
  statusInfoForeground: string;

  statusNeutral: string;
  statusNeutralBackground: string;
  statusNeutralBorder: string;
  statusNeutralForeground: string;
}

export interface ThemeContract {
  colors: SemanticColors;
  typography: typeof primitives.typography;
  spacing: typeof primitives.spacing;
  radius: typeof primitives.radii;
  shadow: typeof primitives.shadows;
  zIndex: typeof primitives.zIndex;
}

// Map the default primitives to semantic purpose for the Mesiri theme
export const defaultSemanticColors: SemanticColors = {
  backgroundApp: primitives.colors.neutral0,
  backgroundSurface: primitives.colors.neutral0,
  backgroundSubtle: primitives.colors.neutral100,
  backgroundInverse: primitives.colors.neutral900,

  textPrimary: primitives.colors.neutral900,
  textSecondary: primitives.colors.neutral700,
  textMuted: primitives.colors.neutral500,
  textInverse: primitives.colors.neutral0,

  borderSubtle: primitives.colors.blackAlpha6,
  borderDefault: primitives.colors.blackAlpha10,
  borderStrong: primitives.colors.neutral900,

  actionPrimary: primitives.colors.lime400,
  actionPrimaryForeground: primitives.colors.neutral900,

  actionSecondary: primitives.colors.neutral100,

  focusRing: primitives.colors.neutral900,

  // Status mapping
  statusSuccess: primitives.colors.green500,
  statusSuccessBackground: '#dcfce7', // Sample subtle green
  statusSuccessBorder: '#bbf7d0',
  statusSuccessForeground: '#15803d',

  statusWarning: primitives.colors.amber500,
  statusWarningBackground: '#fef3c7',
  statusWarningBorder: '#fde68a',
  statusWarningForeground: '#b45309',

  statusDanger: primitives.colors.red500,
  statusDangerBackground: '#fee2e2',
  statusDangerBorder: '#fecaca',
  statusDangerForeground: '#b91c1c',

  statusInfo: primitives.colors.blue500,
  statusInfoBackground: '#dbeafe',
  statusInfoBorder: '#bfdbfe',
  statusInfoForeground: '#1d4ed8',

  statusNeutral: primitives.colors.neutral500,
  statusNeutralBackground: primitives.colors.neutral100,
  statusNeutralBorder: primitives.colors.neutral200,
  statusNeutralForeground: primitives.colors.neutral700,
};

export const mesiriDarkSemanticColors: SemanticColors = {
  backgroundApp: primitives.colors.neutral900,
  backgroundSurface: '#181A20', // slightly elevated from neutral900
  backgroundSubtle: '#21242C', // higher elevation
  backgroundInverse: primitives.colors.neutral0,

  textPrimary: primitives.colors.neutral0,
  textSecondary: primitives.colors.neutral200,
  textMuted: '#9ca3af', // neutral400
  textInverse: primitives.colors.neutral900,

  borderSubtle: 'rgba(255,255,255,0.08)',
  borderDefault: 'rgba(255,255,255,0.12)',
  borderStrong: primitives.colors.neutral200,

  actionPrimary: primitives.colors.lime400,
  actionPrimaryForeground: primitives.colors.neutral900,

  actionSecondary: '#21242C',

  focusRing: primitives.colors.neutral200,

  // Status mapping - slightly adjusted for dark mode readability
  statusSuccess: primitives.colors.green500,
  statusSuccessBackground: 'rgba(34, 197, 94, 0.1)',
  statusSuccessBorder: 'rgba(34, 197, 94, 0.2)',
  statusSuccessForeground: '#4ade80', // green400

  statusWarning: primitives.colors.amber500,
  statusWarningBackground: 'rgba(245, 158, 11, 0.1)',
  statusWarningBorder: 'rgba(245, 158, 11, 0.2)',
  statusWarningForeground: '#fbbf24', // amber400

  statusDanger: primitives.colors.red500,
  statusDangerBackground: 'rgba(239, 68, 68, 0.1)',
  statusDangerBorder: 'rgba(239, 68, 68, 0.2)',
  statusDangerForeground: '#f87171', // red400

  statusInfo: primitives.colors.blue500,
  statusInfoBackground: 'rgba(59, 130, 246, 0.1)',
  statusInfoBorder: 'rgba(59, 130, 246, 0.2)',
  statusInfoForeground: '#60a5fa', // blue400

  statusNeutral: '#9ca3af', // neutral400
  statusNeutralBackground: 'rgba(115, 115, 115, 0.1)',
  statusNeutralBorder: 'rgba(115, 115, 115, 0.2)',
  statusNeutralForeground: primitives.colors.neutral200,
};
