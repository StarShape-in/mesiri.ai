import React from 'react';
import { View, StyleSheet, Platform } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { usePathname, useRouter } from 'expo-router';
import { NAVIGATION_CONFIG } from './navigation.config';
import { MesiriNavItem } from './MesiriNavItem';
import { MesiriAIButton } from './MesiriAIButton';
import { useTheme, useStyles } from '../../src/theme';

export function MesiriBottomNavigation() {
  const insets = useSafeAreaInsets();
  const pathname = usePathname();
  const router = useRouter();
  const { theme } = useTheme();
  const styles = useStyles(createStyles);

  const handlePress = (href: string, isAction?: boolean) => {
    if (isAction) {
      // Open AI interaction surface
      // TODO: Implement actual AI surface trigger
      console.log('Opening Mesiri AI...');
      return;
    }
    router.push(href as any);
  };

  const isActiveRoute = (href: string) => {
    if (href === '/') {
      return pathname === '/';
    }
    return pathname.startsWith(href);
  };

  return (
    <View style={[styles.wrapper, { paddingBottom: Math.max(insets.bottom, 16) }]}>
      <View style={styles.container}>
        {NAVIGATION_CONFIG.map((item) => {
          if (item.isAction) {
            return (
              <MesiriAIButton 
                key={item.id} 
                onPress={() => handlePress(item.href, item.isAction)} 
              />
            );
          }

          return (
            <MesiriNavItem
              key={item.id}
              label={item.label}
              icon={item.icon}
              isActive={isActiveRoute(item.href)}
              onPress={() => handlePress(item.href)}
            />
          );
        })}
      </View>
    </View>
  );
}

const createStyles = (theme: any) => StyleSheet.create({
  wrapper: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    alignItems: 'center',
    pointerEvents: 'box-none',
    zIndex: theme.zIndex.bottomNavigation,
  },
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: theme.components.bottomNavBackground,
    borderRadius: theme.radius.xl, // formerly 32 is higher than xl but it's rounded
    maxWidth: 520,
    width: '92%', // Slight margin on edges for mobile
    height: 72,
    paddingHorizontal: theme.spacing.space3, // 12
    shadowColor: theme.shadow.floating.shadowColor,
    shadowOffset: theme.shadow.floating.shadowOffset,
    shadowOpacity: theme.shadow.floating.shadowOpacity,
    shadowRadius: theme.shadow.floating.shadowRadius,
    elevation: theme.shadow.floating.elevation,
    borderWidth: 1,
    borderColor: theme.colors.borderDefault,
  },
});
