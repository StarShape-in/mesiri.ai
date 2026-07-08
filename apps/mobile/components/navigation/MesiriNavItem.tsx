import React, { useRef } from 'react';
import { View, Text, StyleSheet, Pressable, Animated } from 'react-native';
import { LucideIcon } from 'lucide-react-native';
import { useTheme, useStyles } from '../../src/theme';

export type MesiriNavItemProps = {
  label: string;
  icon: LucideIcon;
  isActive: boolean;
  onPress: () => void;
};

export function MesiriNavItem({ label, icon: Icon, isActive, onPress }: MesiriNavItemProps) {
  const scale = useRef(new Animated.Value(1)).current;
  const { theme } = useTheme();
  const styles = useStyles(createStyles);

  const handlePressIn = () => {
    Animated.timing(scale, {
      toValue: 0.96,
      duration: 100,
      useNativeDriver: true,
    }).start();
  };

  const handlePressOut = () => {
    Animated.timing(scale, {
      toValue: 1,
      duration: 150,
      useNativeDriver: true,
    }).start();
  };

  // Active state renders in the theme's primary color; inactive stays muted.
  const activeColor = theme.colors.actionPrimary;
  const strokeColor = isActive ? activeColor : theme.components.bottomNavInactiveIconStroke;
  const textColor = isActive ? activeColor : theme.components.bottomNavInactiveIconStroke;
  const fontWeight = isActive ? theme.typography.weightSemiBold : theme.typography.weightMedium;

  return (
    <Pressable
      onPress={onPress}
      onPressIn={handlePressIn}
      onPressOut={handlePressOut}
      style={styles.container}
      accessibilityRole="button"
      accessibilityState={{ selected: isActive }}
      aria-label={label}
      aria-current={isActive ? 'page' : undefined}
    >
      <Animated.View style={[styles.content, { transform: [{ scale }] }]}>
        <View
          style={[
            styles.indicator,
            { backgroundColor: isActive ? activeColor : 'transparent' },
          ]}
        />
        <Icon
          size={22}
          stroke={strokeColor}
          strokeWidth={isActive ? 2.5 : 2}
          fill="transparent"
        />
        <Text style={[styles.label, { color: textColor, fontWeight }]} numberOfLines={1}>
          {label}
        </Text>
      </Animated.View>
    </Pressable>
  );
}

const createStyles = (theme: any) => StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 44, // Touch target
  },
  content: {
    alignItems: 'center',
    justifyContent: 'center',
    gap: theme.spacing.space1, // formerly 4
  },
  // Small rounded indicator line sitting above the icon on the active tab.
  indicator: {
    width: 18,
    height: 3,
    borderRadius: theme.radius.full,
    marginBottom: theme.spacing.space1,
  },
  label: {
    fontSize: theme.typography.sizeXs, // roughly 12 or 11
    letterSpacing: -0.2,
  },
});
