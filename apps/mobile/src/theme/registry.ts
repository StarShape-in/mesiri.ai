import { ThemeDefinition } from './types';
import { mesiriThemeDefinition } from './themes/mesiri';
import { oliveGoldThemeDefinition } from './themes/olive-gold';

export const availableThemes: ThemeDefinition[] = [
  mesiriThemeDefinition,
  oliveGoldThemeDefinition,
];
