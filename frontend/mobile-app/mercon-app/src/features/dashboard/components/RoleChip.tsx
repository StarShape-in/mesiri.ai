import React from 'react';
import { Text, View } from 'react-native';
import { ShieldCheck } from 'lucide-react-native';

interface RoleChipProps {
  role: string;
  className?: string;
}

export function RoleChip({ role, className }: RoleChipProps) {
  return (
    <View className={`flex-row items-center gap-1.5 rounded-full bg-primary-light px-3 py-1.5 ${className ?? ''}`}>
      <ShieldCheck size={13} color="#E8450F" strokeWidth={2.2} />
      <Text className="text-xs font-semibold text-primary">{role}</Text>
    </View>
  );
}
