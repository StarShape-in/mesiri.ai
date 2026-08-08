import React from 'react';
import { Text, View } from 'react-native';
import type { LucideIcon } from 'lucide-react-native';

interface InfoRowProps {
  label: string;
  value: string;
  Icon?: LucideIcon;
  className?: string;
}

export function InfoRow({ label, value, Icon, className }: InfoRowProps) {
  return (
    <View className={`flex-row items-center justify-between ${className ?? ''}`}>
      <View className="flex-row items-center gap-1">
        {Icon && <Icon size={12} color="#9898A4" strokeWidth={2} />}
        <Text className="text-[11px] text-gray-400">{label}</Text>
      </View>
      <Text className="text-xs font-semibold text-gray-800">{value}</Text>
    </View>
  );
}
