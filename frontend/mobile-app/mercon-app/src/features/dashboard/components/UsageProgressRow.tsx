import React from 'react';
import { Text, View } from 'react-native';

interface UsageProgressRowProps {
  label: string;
  count: number;
  color: string;
  className?: string;
}

export function UsageProgressRow({ label, count, color, className }: UsageProgressRowProps) {
  return (
    <View className={`flex-row items-center gap-1.5 ${className ?? ''}`}>
      <View style={{ backgroundColor: color }} className="h-2 w-2 rounded-full" />
      <Text className="flex-1 text-[11px] text-gray-500">{label}</Text>
      <Text className="text-xs font-bold text-gray-900">{count}</Text>
    </View>
  );
}
