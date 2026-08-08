import React from 'react';
import { Text, View } from 'react-native';
import type { LucideIcon } from 'lucide-react-native';
import { Colors } from '@/theme/tokens';

interface PerformanceMetricCardProps {
  Icon: LucideIcon;
  /** Already formatted; pass "—" when the metric has no backing data. */
  value: string;
  label: string;
  /** Small clarifier under the label, e.g. the sample size behind a percentage. */
  caption?: string;
  tone?: string;
}

/**
 * One tile in the performance grid. Fixed to just under half the row so the
 * grid stays two even columns instead of a lone tile stretching wide.
 */
export function PerformanceMetricCard({
  Icon,
  value,
  label,
  caption,
  tone = Colors.accent,
}: PerformanceMetricCardProps) {
  return (
    <View style={{ width: '48%' }}>
      <View
        style={{ backgroundColor: `${tone}14` }}
        className="h-9 w-9 items-center justify-center rounded-xl"
      >
        <Icon size={16} color={tone} strokeWidth={2.25} />
      </View>
      <Text numberOfLines={1} className="mt-2.5 text-[20px] font-bold leading-[24px] text-gray-900">
        {value}
      </Text>
      <Text numberOfLines={1} className="mt-0.5 text-[12px] font-semibold text-gray-700">
        {label}
      </Text>
      {caption ? (
        <Text numberOfLines={1} className="mt-0.5 text-[11px] text-gray-400">
          {caption}
        </Text>
      ) : null}
    </View>
  );
}
