import React from 'react';
import { Text, View } from 'react-native';
import { DriverAvatar } from './DriverAvatar';
import { DriverStatusBadge } from './DriverStatusBadge';
import { DriverStatistics } from './DriverStatistics';
import { CARD_SHADOW } from './SectionCard';
import { driverDisplayInitials, driverDisplayName } from '../services/driverDetailsService';
import type { DriverDetail, DriverPerformance } from '../types';

interface DriverProfileCardProps {
  driver: DriverDetail;
  performance: DriverPerformance;
}

/**
 * The screen's hero card: identity on top, headline statistics below a rule.
 *
 * There is no driver-photo column in the backend, so DriverAvatar falls back
 * to initials — it already accepts an `imageUri` for the day one exists.
 */
export function DriverProfileCard({ driver, performance }: DriverProfileCardProps) {
  return (
    <View
      style={{ padding: 20, ...CARD_SHADOW }}
      className="rounded-3xl border border-[#F3F3F3] bg-white"
    >
      <View className="flex-row items-center gap-4">
        <DriverAvatar initials={driverDisplayInitials(driver)} status={driver.status} size={64} />

        {/* min-w-0 lets long names truncate instead of pushing the badge off-card. */}
        <View className="min-w-0 flex-1">
          <Text numberOfLines={1} className="text-[19px] font-bold leading-[24px] text-gray-900">
            {driverDisplayName(driver)}
          </Text>
          <Text numberOfLines={1} className="mt-0.5 text-[12px] font-medium text-gray-400">
            {driver.refId ?? driver.licenseNumber}
          </Text>
          <View className="mt-2 flex-row">
            <DriverStatusBadge status={driver.status} />
          </View>
        </View>
      </View>

      <View className="my-5 h-px bg-[#F3F3F3]" />

      <DriverStatistics
        rating={performance.averageRating}
        totalTrips={performance.totalTrips}
        onTimeRatePct={performance.onTimeRatePct}
      />
    </View>
  );
}
