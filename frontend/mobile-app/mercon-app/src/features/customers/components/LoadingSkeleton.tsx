import React from 'react';
import { View } from 'react-native';
import { SkeletonBlock } from '@/shared/components';

/** Mirrors CustomerCard's geometry so nothing shifts when the real rows land. */
export function SkeletonCustomerCard() {
  return (
    <View style={{ padding: 20 }} className="rounded-3xl border border-[#F3F3F3] bg-white">
      <View className="flex-row items-start">
        <SkeletonBlock width={48} height={48} radius={24} />
        <View className="flex-1 px-3">
          <SkeletonBlock width="70%" height={16} />
          <View className="mt-2">
            <SkeletonBlock width="45%" height={12} />
          </View>
          <View className="mt-2">
            <SkeletonBlock width={58} height={18} radius={9} />
          </View>
        </View>
        <View className="items-end gap-2">
          <SkeletonBlock width={38} height={19} />
          <SkeletonBlock width={62} height={14} />
        </View>
      </View>

      <View className="my-4 h-px bg-[#F3F3F3]" />

      <View className="flex-row flex-wrap justify-between" style={{ rowGap: 14 }}>
        {[0, 1, 2, 3].map((i) => (
          <View key={i} style={{ width: '48%' }} className="gap-1.5">
            <SkeletonBlock width="60%" height={10} />
            <SkeletonBlock width="85%" height={13} />
          </View>
        ))}
      </View>

      <View className="mt-5 flex-row" style={{ gap: 10 }}>
        <SkeletonBlock width="48%" height={44} radius={16} />
        <SkeletonBlock width="48%" height={44} radius={16} />
      </View>
    </View>
  );
}
