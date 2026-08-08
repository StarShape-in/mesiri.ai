import React from 'react';
import { Text, View } from 'react-native';
import type { LucideIcon } from 'lucide-react-native';
import { Colors } from '@/theme/tokens';

interface CustomerStatCardProps {
  Icon: LucideIcon;
  value: string;
  label: string;
  /** Small clarifier, e.g. the period a figure covers. */
  caption?: string;
  width?: number;
}

/**
 * Dark KPI tile with an orange indicator rule. Matches the dark stat tiles
 * already used on the Drivers list so the two screens read as one system.
 */
export function CustomerStatCard({ Icon, value, label, caption, width = 150 }: CustomerStatCardProps) {
  return (
    <View
      style={{ width, backgroundColor: Colors.navBg, padding: 18 }}
      className="rounded-[22px]"
    >
      <View
        style={{ backgroundColor: 'rgba(255,255,255,0.08)' }}
        className="h-11 w-11 items-center justify-center rounded-2xl"
      >
        <Icon size={19} color={Colors.white} strokeWidth={2} />
      </View>

      <Text numberOfLines={1} className="mt-5 text-[26px] font-bold leading-[30px] text-white">
        {value}
      </Text>
      <Text numberOfLines={2} className="mt-0.5 text-[12px] font-medium leading-[16px] text-white/60">
        {label}
      </Text>

      {/* Orange indicator rule */}
      <View style={{ width: 34, height: 3, backgroundColor: Colors.accent }} className="mt-3 rounded-full" />

      {caption ? (
        <Text numberOfLines={1} className="mt-2 text-[11px] text-white/40">
          {caption}
        </Text>
      ) : null}
    </View>
  );
}
