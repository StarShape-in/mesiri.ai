import React from 'react';
import { Text, TouchableOpacity } from 'react-native';
import type { LucideIcon } from 'lucide-react-native';

interface DriverActionButtonProps {
  label: string;
  Icon: LucideIcon;
  onPress?: () => void;
  disabled?: boolean;
  className?: string;
}

/** Rounded white action button — icon + label side by side, used inside DriverActionGroup. */
export function DriverActionButton({ label, Icon, onPress, disabled, className }: DriverActionButtonProps) {
  return (
    <TouchableOpacity
      onPress={onPress}
      disabled={disabled || !onPress}
      activeOpacity={0.75}
      className={`flex-row items-center justify-center gap-1.5 rounded-xl border border-gray-100 bg-white py-2.5 ${disabled ? 'opacity-40' : ''} ${className ?? ''}`}
      style={{ shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.05, shadowRadius: 4, elevation: 1 }}
    >
      <Icon size={15} color="#F24822" strokeWidth={2.25} />
      <Text className="text-xs font-semibold text-gray-700">{label}</Text>
    </TouchableOpacity>
  );
}
