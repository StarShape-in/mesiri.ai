import React from 'react';
import { View } from 'react-native';
import { Truck, Users } from 'lucide-react-native';
import { DriverStatCard } from './DriverStatCard';
import { SkeletonDriverStatCard } from './LoadingSkeleton';
import { ErrorState } from '@/shared/components';
import { useDriverStats } from '../hooks';

/**
 * Two headline KPIs side by side. The remaining counts (available / offline)
 * ride along as each card's caption rather than adding more cards, which kept
 * the row from feeling crowded.
 */
export function DriverStatsSection() {
  const stats = useDriverStats();

  if (stats.loading) {
    return (
      <View className="flex-row gap-3">
        <SkeletonDriverStatCard />
        <SkeletonDriverStatCard />
      </View>
    );
  }

  if (stats.error) {
    return <ErrorState message={stats.error} onRetry={() => stats.refresh()} />;
  }

  return (
    <View className="flex-row gap-3">
      <DriverStatCard
        label="Total Drivers"
        value={stats.totalDrivers}
        Icon={Users}
        caption={`${stats.online} available`}
      />
      <DriverStatCard
        label="On Trip"
        value={stats.onTrip}
        Icon={Truck}
        caption={`${stats.offline} offline`}
      />
    </View>
  );
}
