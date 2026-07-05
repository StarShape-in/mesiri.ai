import { SemanticColors, ThemeContract } from './tokens/semantic';
import { ComponentColors } from './tokens/components';

export type AppearanceMode = 'system' | 'light' | 'dark';
export type ResolvedAppearance = 'light' | 'dark';

export interface ThemePreviewDefinition {
  primary: string;
  primaryStrong: string;
  primaryBright: string;
  surface: string;
  foreground: string;
}

export interface ThemeDefinition {
  id: string;
  name: string;
  description: string;
  light: SemanticColors;
  dark: SemanticColors;
  preview: ThemePreviewDefinition;
}

export interface ThemeContextType {
  theme: ThemeContract & { id: string; components: ComponentColors };
  themeId: string;
  appearance: AppearanceMode;
  resolvedAppearance: ResolvedAppearance;
  availableThemes: ThemeDefinition[];
  setThemeId: (id: string) => void;
  setAppearance: (mode: AppearanceMode) => void;
}
