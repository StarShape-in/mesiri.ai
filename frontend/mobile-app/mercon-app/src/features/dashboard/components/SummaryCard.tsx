import React from 'react';
import { Text, View } from 'react-native';
import type { LucideIcon } from 'lucide-react-native';

interface SummaryCardProps {
  label: string;
  value: string;
  Icon: LucideIcon;
  className?: string;
}

export function SummaryCard({ label, value, Icon, className }: SummaryCardProps) {
  return (
    <View className={`flex-1 items-center gap-1.5 rounded-2xl bg-navbg px-3 py-4 ${className ?? ''}`}>
      <Icon size={18} color="#FFFFFF" strokeWidth={2} />
      <Text className="text-lg font-extrabold text-white">{value}</Text>
      <Text className="text-center text-[10px] text-white/60">{label}</Text>
    </View>
  );
}
