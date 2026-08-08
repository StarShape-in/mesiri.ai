import React from 'react';
import { Text, View } from 'react-native';
import { Truck } from 'lucide-react-native';
import { CircularProgress } from './CircularProgress';
import { UsageProgressRow } from './UsageProgressRow';
import type { FleetCategoryUtilization } from '../types';

interface FleetUtilizationCardProps {
  category: FleetCategoryUtilization;
  className?: string;
}

export function FleetUtilizationCard({ category, className }: FleetUtilizationCardProps) {
  return (
    <View className={`w-48 items-center gap-3 rounded-2xl border border-black/5 bg-white p-4 ${className ?? ''}`}>
      <View className="h-11 w-11 items-center justify-center rounded-xl bg-gray-100">
        <Truck size={22} color="#3B3B44" strokeWidth={1.75} />
      </View>

      <View className="items-center">
        <Text className="text-sm font-bold text-gray-900">{category.assetType}</Text>
        <Text className="text-[11px] text-gray-500">{category.totalTrucks} trucks total</Text>
      </View>

      <CircularProgress progress={category.utilization} label="Utilized" />

      <View className="w-full gap-1.5">
        <UsageProgressRow label="In Use" count={category.inUse} color="#2563EB" />
        <UsageProgressRow label="Idle" count={category.idle} color="#9898A4" />
        <UsageProgressRow label="Maintenance" count={category.maintenance} color="#D97706" />
      </View>
    </View>
  );
}
