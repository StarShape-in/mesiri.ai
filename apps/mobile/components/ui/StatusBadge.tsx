import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

export type StatusType = 'critical' | 'warning' | 'success' | 'neutral';

type StatusBadgeProps = {
  status: StatusType;
  label: string;
};

export function StatusBadge({ status, label }: StatusBadgeProps) {
  const getColors = () => {
    switch (status) {
      case 'critical':
        return { bg: '#FEE2E2', text: '#991B1B', dot: '#DC2626' }; // Red
      case 'warning':
        return { bg: '#FEF3C7', text: '#92400E', dot: '#D97706' }; // Amber
      case 'success':
        return { bg: '#E4F8B3', text: '#3E5C0A', dot: '#65A30D' }; // Mesiri Lime variant
      case 'neutral':
      default:
        return { bg: '#F3F3F3', text: '#525252', dot: '#737373' }; // Gray
    }
  };

  const colors = getColors();

  return (
    <View style={[styles.badge, { backgroundColor: colors.bg }]}>
      <View style={[styles.dot, { backgroundColor: colors.dot }]} />
      <Text style={[styles.label, { color: colors.text }]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
    alignSelf: 'flex-start',
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    marginRight: 6,
  },
  label: {
    fontSize: 11,
    fontWeight: '600',
    letterSpacing: 0.2,
  },
});
