import React from 'react';
import { Text, View } from 'react-native';
import type { LucideIcon } from 'lucide-react-native';

interface DocumentSummaryCardProps {
  label: string;
  count: number;
  Icon: LucideIcon;
  tone: 'warning' | 'danger' | 'success';
  className?: string;
}

const TONE_COLORS: Record<DocumentSummaryCardProps['tone'], { bg: string; color: string }> = {
  warning: { bg: '#FFFBEB', color: '#D97706' },
  danger:  { bg: '#FEF2F2', color: '#DC2626' },
  success: { bg: '#F0FDF4', color: '#16A34A' },
};

export function DocumentSummaryCard({ label, count, Icon, tone, className }: DocumentSummaryCardProps) {
  const { bg, color } = TONE_COLORS[tone];
  return (
    <View
      className={`flex-1 gap-2 rounded-2xl border border-[#F3F3F3] bg-white p-3.5 ${className ?? ''}`}
      style={{ shadowColor: '#000', shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.05, shadowRadius: 10, elevation: 2 }}
    >
      <View style={{ backgroundColor: bg }} className="h-8 w-8 items-center justify-center rounded-full">
        <Icon size={16} color={color} strokeWidth={2.25} />
      </View>
      <Text className="text-xl font-extrabold text-gray-900">{count}</Text>
      <Text numberOfLines={1} className="text-[11px] text-gray-500">{label}</Text>
    </View>
  );
}
