import { useMemo } from 'react';
import { StyleSheet } from 'react-native';
import { useTheme } from './ThemeProvider';
import { MesiriTheme } from './themes/mesiri';

/**
 * A hook that takes a style factory function and returns the compiled StyleSheet.
 * It automatically re-evaluates when the theme changes.
 * 
 * @param styleFactory A function that receives the current theme and returns a StyleSheet object.
 */
export const useStyles = <T extends StyleSheet.NamedStyles<T> | StyleSheet.NamedStyles<any>>(
  styleFactory: (theme: MesiriTheme) => T
): T => {
  const { theme } = useTheme();
  
  return useMemo(() => {
    // Cast the returned object so TS doesn't complain about 'string' not being 'FlexAlignType'
    return StyleSheet.create(styleFactory(theme)) as T;
  }, [theme, styleFactory]);
};
