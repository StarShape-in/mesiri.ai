import React from 'react';
import { View, Text, StyleSheet, ViewStyle } from 'react-native';
import { Colors, Spacing, Radius, Typography, getStatusColors } from '../theme/tokens';

type BadgeVariant = 'success' | 'warning' | 'danger' | 'info' | 'neutral';

const VARIANT_COLORS: Record<BadgeVariant, { color: string; bg: string }> = {
  success: { color: Colors.success, bg: Colors.successLight },
  warning: { color: Colors.warning, bg: Colors.warningLight },
  danger:  { color: Colors.danger,  bg: Colors.dangerLight  },
  info:    { color: Colors.info,    bg: Colors.infoLight    },
  neutral: { color: Colors.statusPending, bg: Colors.statusPendingBg },
};

interface BadgeProps {
  label: string;
  /** Shorthand for a color+bg pair; overridden by explicit color/bg. */
  variant?: BadgeVariant;
  color?: string;
  bg?: string;
  dot?: boolean;
  style?: ViewStyle;
}

/** Generic badge — pass variant, or color + bg, or use StatusBadge for automatic status colors */
export function Badge({ label, variant, color, bg, dot, style }: BadgeProps) {
  const v = variant ? VARIANT_COLORS[variant] : null;
  color = color ?? v?.color ?? Colors.statusPending;
  bg = bg ?? v?.bg ?? Colors.statusPendingBg;
  return (
    <View style={[styles.badge, { backgroundColor: bg }, style]}>
      {dot && <View style={[styles.dot, { backgroundColor: color }]} />}
      <Text style={[styles.text, { color }]}>{label}</Text>
    </View>
  );
}

/** Automatically picks colors based on trip/vehicle/document status string */
export function StatusBadge({ status, dot, style }: { status: string; label?: string; dot?: boolean; style?: ViewStyle }) {
  const { color, bg } = getStatusColors(status);
  return <Badge label={status} color={color} bg={bg} dot={dot} style={style} />;
}

/** Solid colored badge (e.g. Priority: Critical) */
export function SolidBadge({ label, color = Colors.danger, style }: { label: string; color?: string; style?: ViewStyle }) {
  return (
    <View style={[styles.badge, { backgroundColor: color }, style]}>
      <Text style={[styles.text, { color: Colors.white }]}>{label}</Text>
    </View>
  );
}

/** Filter chip — toggleable */
export function FilterChip({
  label, active, onPress, style,
}: { label: string; active?: boolean; onPress?: () => void; style?: ViewStyle }) {
  return (
    <View
      onTouchEnd={onPress}
      style={[
        styles.chip,
        active
          ? { backgroundColor: Colors.primary }
          : { backgroundColor: Colors.gray100 },
        style,
      ]}
    >
      <Text style={[styles.chipText, { color: active ? Colors.white : Colors.dark }]}>
        {label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    paddingHorizontal: Spacing.sm + 2,
    paddingVertical: Spacing.xs / 2,
    borderRadius: Radius.full,
    gap: 4,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  text: {
    ...Typography.caption,
    fontWeight: '600',
  },
  chip: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.xs + 1,
    borderRadius: Radius.full,
  },
  chipText: {
    ...Typography.bodySmall,
    fontWeight: '600',
  },
});
