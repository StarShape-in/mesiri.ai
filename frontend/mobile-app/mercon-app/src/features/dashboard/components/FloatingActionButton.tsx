import React from 'react';
import { TouchableOpacity } from 'react-native';
import { Plus, type LucideIcon } from 'lucide-react-native';

interface FloatingActionButtonProps {
  onPress?: () => void;
  Icon?: LucideIcon;
  size?: number;
  className?: string;
}

/** Generic reusable FAB. The live app renders its floating action button as part of the global OperatorBottomNav (src/navigation/OperatorBottomNav.tsx) so it stays fixed across every tab — this component exists for reuse anywhere else a standalone FAB is needed. */
export function FloatingActionButton({ onPress, Icon = Plus, size = 52, className }: FloatingActionButtonProps) {
  return (
    <TouchableOpacity
      onPress={onPress}
      activeOpacity={0.85}
      accessibilityRole="button"
      style={{ width: size, height: size, borderRadius: size / 2 }}
      className={`items-center justify-center border-2 border-primary bg-white ${className ?? ''}`}
    >
      <Icon size={Math.round(size * 0.5)} color="#E8450F" strokeWidth={2.6} />
    </TouchableOpacity>
  );
}
