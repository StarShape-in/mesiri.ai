import React from 'react';
import { View } from 'react-native';
import { SkeletonBlock } from '@/shared/components';

export function SkeletonDocumentSummaryCard() {
  return (
    <View className="flex-1 gap-2 rounded-2xl border border-[#F3F3F3] bg-white p-3.5">
      <SkeletonBlock width={32} height={32} radius={16} />
      <SkeletonBlock width={30} height={22} />
      <SkeletonBlock width="70%" height={11} />
    </View>
  );
}

export function SkeletonDocumentExpiryCard() {
  return (
    <View className="gap-3 rounded-3xl border border-[#F3F3F3] bg-white p-[18px]">
      <View className="flex-row items-center gap-3">
        <SkeletonBlock width={44} height={44} radius={22} />
        <View className="flex-1 gap-1.5">
          <SkeletonBlock width="55%" height={14} />
          <SkeletonBlock width="40%" height={10} />
          <SkeletonBlock width="65%" height={10} />
        </View>
        <SkeletonBlock width={70} height={20} radius={10} />
      </View>
      <SkeletonBlock height={4} radius={2} />
    </View>
  );
}
