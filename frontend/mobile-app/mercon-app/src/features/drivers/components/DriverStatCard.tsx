import React from 'react';
import { Text, View } from 'react-native';
import type { LucideIcon } from 'lucide-react-native';

interface DriverStatCardProps {
  label: string;
  value: number;
  Icon: LucideIcon;
  /** Small secondary line under the label, e.g. "32 available". */
  caption?: string;
  className?: string;
}

/** Compact horizontal KPI tile — icon left, value + label + caption right. */
export function DriverStatCard({ label, value, Icon, caption, className }: DriverStatCardProps) {
  return (
    <View className={`flex-1 flex-row items-center gap-3 overflow-hidden rounded-2xl bg-navbg py-4 pl-4 pr-3 ${className ?? ''}`}>
      <View className="h-11 w-11 items-center justify-center rounded-full bg-white/10">
        <Icon size={19} color="#F24822" strokeWidth={2.2} />
      </View>

      <View className="flex-1 gap-0.5">
        <Text numberOfLines={1} className="text-2xl font-extrabold leading-[26px] text-white">
          {value.toLocaleString()}
        </Text>
        <Text numberOfLines={1} className="text-xs font-medium text-white/60">{label}</Text>
        {caption ? (
          <Text numberOfLines={1} className="mt-0.5 text-[10px] text-white/35">{caption}</Text>
        ) : null}
      </View>
    </View>
  );
}
