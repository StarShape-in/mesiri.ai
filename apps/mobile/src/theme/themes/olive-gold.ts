import { SemanticColors, defaultSemanticColors, mesiriDarkSemanticColors } from '../tokens/semantic';
import { primitives } from '../tokens/primitives';
import { ThemeDefinition } from '../types';

export const oliveGoldLightColors: SemanticColors = {
  ...defaultSemanticColors,
  
  // Olive Gold Overrides
  actionPrimary: '#FFD700', // Golden Yellow
  actionPrimaryForeground: primitives.colors.neutral900,
  
  backgroundSubtle: '#E8E8E8', // Light Gray / Off White
  
  textMuted: '#A6A6A6', // Medium Gray
  
  // Rare Highlighted Surfaces
  // Use existing dark inverse tokens so it remains a high-contrast component
  actionSecondary: '#E8E8E8', // For subtle actions
};

export const oliveGoldDarkColors: SemanticColors = {
  ...mesiriDarkSemanticColors,
  
  // Olive Gold Overrides
  actionPrimary: '#FFD700', // Golden Yellow
  actionPrimaryForeground: primitives.colors.neutral900,
  
  backgroundSubtle: '#21242C', // Using deep gray to keep dark mode clean, don't use light gray
  
  textMuted: '#A6A6A6', // Medium Gray contrast in dark mode is usually acceptable but keep an eye
  
  actionSecondary: '#21242C',
};

export const oliveGoldThemeDefinition: ThemeDefinition = {
  id: 'olive-gold',
  name: 'Olive Gold',
  description: 'Gold, yellow and neutral system',
  light: oliveGoldLightColors,
  dark: oliveGoldDarkColors,
  preview: {
    primary: '#FFD700',
    primaryStrong: '#B99E00',
    primaryBright: '#FFEE00',
    surface: '#E8E8E8',
    foreground: '#A6A6A6',
  }
};
