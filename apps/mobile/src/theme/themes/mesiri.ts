import { ThemeContract, defaultSemanticColors, mesiriDarkSemanticColors } from '../tokens/semantic';
import { createComponentColors, ComponentColors } from '../tokens/components';
import { primitives } from '../tokens/primitives';
import { ThemeDefinition } from '../types';

export interface MesiriTheme extends ThemeContract {
  components: ComponentColors;
  id: string;
}

export const mesiriThemeDefinition: ThemeDefinition = {
  id: 'mesiri',
  name: 'Mesiri Default',
  description: "Mesiri's signature lime and black system",
  light: defaultSemanticColors,
  dark: mesiriDarkSemanticColors,
  preview: {
    primary: primitives.colors.lime400,
    primaryStrong: '#84cc16', // slightly darker lime
    primaryBright: '#bef264',
    surface: primitives.colors.neutral0,
    foreground: primitives.colors.neutral900,
  }
};
