import React from 'react';
import { TouchableOpacity, View } from 'react-native';
import type { LucideIcon } from 'lucide-react-native';

interface IconButtonProps {
  Icon: LucideIcon;
  onPress?: () => void;
  size?: number;
  iconColor?: string;
  iconSize?: number;
  className?: string;
  badge?: boolean;
  /** White background + soft shadow instead of the flat grey fill. */
  elevated?: boolean;
}

export function IconButton({
  Icon, onPress, size = 40, iconColor = '#111111', iconSize = 20, className, badge, elevated,
}: IconButtonProps) {
  return (
    <TouchableOpacity
      onPress={onPress}
      activeOpacity={0.7}
      accessibilityRole="button"
      style={{
        width: size,
        height: size,
        ...(elevated
          ? { shadowColor: '#000', shadowOffset: { width: 0, height: 3 }, shadowOpacity: 0.08, shadowRadius: 8, elevation: 2 }
          : null),
      }}
      className={`items-center justify-center rounded-full ${elevated ? 'bg-white' : 'bg-gray-100'} ${className ?? ''}`}
    >
      <Icon size={iconSize} color={iconColor} strokeWidth={2} />
      {badge && <View className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-primary" />}
    </TouchableOpacity>
  );
}
