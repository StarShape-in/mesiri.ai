import React, { createContext, useContext, useState, useEffect, ReactNode, useMemo } from 'react';
import { useColorScheme } from 'react-native';
import * as SecureStore from 'expo-secure-store';
import { ThemeContextType, AppearanceMode, ResolvedAppearance, ThemeDefinition } from './types';
import { availableThemes } from './registry';
import { createComponentColors } from './tokens/components';
import { primitives } from './tokens/primitives';

const THEME_STORAGE_KEY = 'mesiri_theme_id';
const APPEARANCE_STORAGE_KEY = 'mesiri_appearance_mode';

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const ThemeProvider = ({ children }: { children: ReactNode }) => {
  const systemColorScheme = useColorScheme(); // 'light' | 'dark'
  const [themeId, setThemeIdState] = useState<string>('mesiri');
  const [appearance, setAppearanceState] = useState<AppearanceMode>('system');
  const [isReady, setIsReady] = useState(false);

  // Load preferences from secure store
  useEffect(() => {
    async function loadPreferences() {
      try {
        const storedThemeId = await SecureStore.getItemAsync(THEME_STORAGE_KEY);
        const storedAppearance = await SecureStore.getItemAsync(APPEARANCE_STORAGE_KEY);
        
        if (storedThemeId && availableThemes.some(t => t.id === storedThemeId)) {
          setThemeIdState(storedThemeId);
        }
        
        if (storedAppearance === 'system' || storedAppearance === 'light' || storedAppearance === 'dark') {
          setAppearanceState(storedAppearance);
        }
      } catch (e) {
        console.warn('Failed to load theme preferences', e);
      } finally {
        setIsReady(true);
      }
    }
    loadPreferences();
  }, []);

  const setThemeId = (id: string) => {
    if (availableThemes.some(t => t.id === id)) {
      setThemeIdState(id);
      SecureStore.setItemAsync(THEME_STORAGE_KEY, id).catch(e => console.warn(e));
    }
  };

  const setAppearance = (mode: AppearanceMode) => {
    setAppearanceState(mode);
    SecureStore.setItemAsync(APPEARANCE_STORAGE_KEY, mode).catch(e => console.warn(e));
  };

  const resolvedAppearance: ResolvedAppearance = useMemo(() => {
    if (appearance === 'system') {
      return systemColorScheme === 'dark' ? 'dark' : 'light';
    }
    return appearance;
  }, [appearance, systemColorScheme]);

  const activeTheme = useMemo(() => {
    const themeDef = availableThemes.find(t => t.id === themeId) || availableThemes[0];
    const colors = resolvedAppearance === 'dark' ? themeDef.dark : themeDef.light;
    
    return {
      id: themeDef.id,
      colors,
      components: createComponentColors(colors),
      typography: primitives.typography,
      spacing: primitives.spacing,
      radius: primitives.radii,
      shadow: primitives.shadows,
      zIndex: primitives.zIndex,
    };
  }, [themeId, resolvedAppearance]);

  if (!isReady) return null; // Prevent flash of wrong theme

  return (
    <ThemeContext.Provider value={{
      theme: activeTheme,
      themeId,
      appearance,
      resolvedAppearance,
      availableThemes,
      setThemeId,
      setAppearance
    }}>
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = (): ThemeContextType => {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};
