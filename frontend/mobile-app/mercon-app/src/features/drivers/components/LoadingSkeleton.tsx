import React from 'react';
import { View } from 'react-native';
import { SkeletonBlock } from '@/shared/components';

export function SkeletonDriverStatCard() {
  return (
    <View className="flex-1 flex-row items-center gap-3 rounded-2xl bg-navbg py-4 pl-4 pr-3">
      <SkeletonBlock width={44} height={44} radius={22} className="bg-white/10" />
      <View className="flex-1 gap-1">
        <SkeletonBlock width={46} height={22} className="bg-white/10" />
        <SkeletonBlock width="70%" height={11} className="bg-white/10" />
      </View>
    </View>
  );
}

/**
 * Mirrors the Driver Details section rhythm — same card radius, border and
 * spacing — so nothing shifts when the real data lands. Assumes the parent
 * ScrollView already applies the screen's horizontal padding.
 */
export function SkeletonDriverDetails() {
  return (
    <View style={{ gap: 20 }}>
      {/* Profile card */}
      <View style={{ padding: 20 }} className="rounded-3xl border border-[#F3F3F3] bg-white">
        <View className="flex-row items-center">
          <SkeletonBlock width={64} height={64} radius={18} />
          <View className="flex-1 pl-4">
            <SkeletonBlock width="65%" height={19} />
            <View className="mt-2">
              <SkeletonBlock width="35%" height={12} />
            </View>
            <View className="mt-2.5">
              <SkeletonBlock width={84} height={22} radius={11} />
            </View>
          </View>
        </View>
        <View className="my-5 h-px bg-[#F3F3F3]" />
        <View className="flex-row">
          {[0, 1, 2].map((i) => (
            <View key={i} className="flex-1 items-center">
              <SkeletonBlock width={15} height={15} radius={8} />
              <View className="mt-2">
                <SkeletonBlock width={44} height={22} />
              </View>
              <View className="mt-1.5">
                <SkeletonBlock width={58} height={11} />
              </View>
            </View>
          ))}
        </View>
      </View>

      {/* Section blocks: header line + card */}
      {[96, 132, 150].map((h, i) => (
        <View key={i} style={{ gap: 12 }}>
          <SkeletonBlock width={140} height={16} />
          <View style={{ padding: 18 }} className="rounded-3xl border border-[#F3F3F3] bg-white">
            <SkeletonBlock height={h} radius={14} />
          </View>
        </View>
      ))}
    </View>
  );
}

export function SkeletonDriverCard() {
  return (
    <View className="flex-row gap-3 rounded-3xl border border-[#F3F3F3] bg-white p-[18px]">
      <SkeletonBlock width={64} height={64} radius={18} />
      <View className="flex-1 gap-2">
        <SkeletonBlock width="60%" height={16} />
        <SkeletonBlock width={70} height={18} radius={9} />
        <SkeletonBlock width="50%" height={10} />
        <SkeletonBlock width="40%" height={10} />
      </View>
      <View className="items-end gap-2">
        <SkeletonBlock width={40} height={12} />
        <SkeletonBlock width={64} height={36} radius={12} />
        <SkeletonBlock width={64} height={36} radius={12} />
      </View>
    </View>
  );
}
