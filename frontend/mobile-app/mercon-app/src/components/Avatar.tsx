import React from 'react';
import { View, Text, StyleSheet, ViewStyle } from 'react-native';
import { Colors, Radius, Typography } from '../theme/tokens';

type AvatarSize = 'sm' | 'md' | 'lg' | 'xl' | number;
type OnlineStatus = 'online' | 'busy' | 'offline';

interface AvatarProps {
  initials: string;
  color?: string;
  size?: AvatarSize;
  onlineStatus?: OnlineStatus;
  style?: ViewStyle;
}

type NamedSize = 'sm' | 'md' | 'lg' | 'xl';
const SIZE_MAP: Record<NamedSize, number> = { sm: 28, md: 36, lg: 48, xl: 64 };
const FONT_MAP: Record<NamedSize, number> = { sm: 10, md: 12, lg: 14, xl: 18 };
const DOT_MAP:  Record<NamedSize, number> = { sm: 8,  md: 10, lg: 12, xl: 14 };

const STATUS_COLORS: Record<OnlineStatus, string> = {
  online:  Colors.success,
  busy:    Colors.warning,
  offline: Colors.gray400,
};

export function Avatar({ initials, color = Colors.primary, size = 'md', onlineStatus, style }: AvatarProps) {
  const isNum = typeof size === 'number';
  const diameter = isNum ? size : SIZE_MAP[size];
  const dotSize  = isNum ? Math.round(size * 0.28) : DOT_MAP[size];
  const fontSize = isNum ? Math.round(size * 0.36) : FONT_MAP[size];

  return (
    <View style={[{ position: 'relative', width: diameter, height: diameter }, style]}>
      <View style={[styles.avatar, { width: diameter, height: diameter, borderRadius: diameter / 2, backgroundColor: color }]}>
        <Text style={{ fontSize, fontWeight: '700', color: Colors.white }}>
          {initials}
        </Text>
      </View>
      {onlineStatus && (
        <View style={[
          styles.dot,
          {
            width: dotSize, height: dotSize, borderRadius: dotSize / 2,
            backgroundColor: STATUS_COLORS[onlineStatus],
            bottom: 0, right: 0,
          },
        ]} />
      )}
    </View>
  );
}

/** Stack of overlapping avatars */
export function AvatarGroup({ items, max = 5 }: { items: { initials: string; color?: string }[]; max?: number }) {
  const visible = items.slice(0, max);
  const overflow = items.length - max;

  return (
    <View style={stackStyles.row}>
      {visible.map((item, i) => (
        <View key={i} style={[stackStyles.item, { marginLeft: i === 0 ? 0 : -8, zIndex: visible.length - i }]}>
          <Avatar initials={item.initials} color={item.color} size="md" />
        </View>
      ))}
      {overflow > 0 && (
        <View style={[stackStyles.overflow, { marginLeft: -8 }]}>
          <Text style={stackStyles.overflowText}>+{overflow}</Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  avatar: { alignItems: 'center', justifyContent: 'center' },
  dot: {
    position: 'absolute',
    borderWidth: 2,
    borderColor: Colors.white,
  },
});

const stackStyles = StyleSheet.create({
  row:          { flexDirection: 'row', alignItems: 'center' },
  item:         {},
  overflow:     { width: 36, height: 36, borderRadius: 18, backgroundColor: Colors.gray200, alignItems: 'center', justifyContent: 'center', borderWidth: 2, borderColor: Colors.white },
  overflowText: { fontSize: 12, fontWeight: '700', color: Colors.gray500 },
});
