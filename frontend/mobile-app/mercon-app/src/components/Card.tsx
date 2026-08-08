import React from 'react';
import { View, StyleSheet, ViewStyle } from 'react-native';
import { Colors, Radius, Shadows } from '../theme/tokens';

interface CardProps {
  children: React.ReactNode;
  style?: ViewStyle;
  variant?: 'default' | 'dark';
  elevated?: boolean;
}

export function Card({ children, style, variant = 'default', elevated = false }: CardProps) {
  return (
    <View
      style={[
        styles.card,
        variant === 'dark' && styles.dark,
        elevated && Shadows.md,
        !elevated && Shadows.sm,
        style,
      ]}
    >
      {children}
    </View>
  );
}

/** Dark stat card used in dashboard/home */
export function DarkCard({ children, style }: { children: React.ReactNode; style?: ViewStyle }) {
  return (
    <View style={[styles.darkCard, Shadows.md, style]}>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Colors.white,
    borderRadius: Radius['2xl'],
    borderWidth: 1,
    borderColor: 'rgba(0,0,0,0.07)',
    overflow: 'hidden',
  },
  dark: {
    backgroundColor: Colors.darkCard,
    borderColor: 'transparent',
  },
  darkCard: {
    backgroundColor: Colors.darkCard,
    borderRadius: Radius['2xl'],
    overflow: 'hidden',
  },
});
