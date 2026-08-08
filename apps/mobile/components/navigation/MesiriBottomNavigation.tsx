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
    <View style={[styles.bar, { paddingBottom: insets.bottom }]}>
      <View style={styles.row}>
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
  // Full-width bar attached to the bottom edge with a subtle top divider.
  bar: {
    backgroundColor: theme.components.bottomNavBackground,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: theme.colors.borderSubtle,
    zIndex: theme.zIndex.bottomNavigation,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'stretch',
    height: 60,
    paddingHorizontal: theme.spacing.space2, // 8
  },
});
