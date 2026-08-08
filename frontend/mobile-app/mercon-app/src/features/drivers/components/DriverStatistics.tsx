import React from 'react';
import { Text, View } from 'react-native';
import { Clock, Star, Truck } from 'lucide-react-native';
import type { LucideIcon } from 'lucide-react-native';
import { Colors } from '@/theme/tokens';

interface StatProps {
  Icon: LucideIcon;
  value: string;
  label: string;
}

function Stat({ Icon, value, label }: StatProps) {
  return (
    <View className="flex-1 items-center">
      <Icon size={15} color={Colors.accent} strokeWidth={2.25} />
      <Text numberOfLines={1} className="mt-2 text-[22px] font-bold leading-[26px] text-gray-900">
        {value}
      </Text>
      <Text numberOfLines={1} className="mt-1 text-[11px] font-medium text-gray-400">
        {label}
      </Text>
    </View>
  );
}

interface DriverStatisticsProps {
  /** Null renders "—" — there is no rating column in the backend. */
  rating: number | null;
  totalTrips: number;
  /** Null renders "—" when no completed trip has both a planned and an actual end time. */
  onTimeRatePct: number | null;
}

/** Three equal columns, separated by full-height hairlines. */
export function DriverStatistics({ rating, totalTrips, onTimeRatePct }: DriverStatisticsProps) {
  return (
    <View className="flex-row">
      <Stat Icon={Star} value={rating !== null ? rating.toFixed(1) : '—'} label="Rating" />
      {/* Explicit height: a 1px view with no content has nothing to stretch against. */}
      <View style={{ width: 1, height: 46 }} className="self-center bg-[#F3F3F3]" />
      <Stat Icon={Truck} value={String(totalTrips)} label="Total Trips" />
      <View style={{ width: 1, height: 46 }} className="self-center bg-[#F3F3F3]" />
      <Stat
        Icon={Clock}
        value={onTimeRatePct !== null ? `${onTimeRatePct}%` : '—'}
        label="On-Time Rate"
      />
    </View>
  );
}
