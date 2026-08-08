/** Pulsing placeholder block used while a query is loading. */
import React, { useEffect, useRef } from 'react';
import { Animated, View } from 'react-native';

interface SkeletonBlockProps {
  width?: number | `${number}%`;
  height?: number;
  radius?: number;
  className?: string;
}

export function SkeletonBlock({ width = '100%', height = 16, radius = 8, className }: SkeletonBlockProps) {
  const opacity = useRef(new Animated.Value(0.35)).current;

  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, { toValue: 0.8, duration: 650, useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 0.35, duration: 650, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [opacity]);

  return (
    <Animated.View
      className={`bg-gray-200 ${className ?? ''}`}
      style={{ width, height, borderRadius: radius, opacity }}
    />
  );
}

/** Skeleton for a DashboardMetricCard. */
export function SkeletonMetricCard() {
  return (
    <View className="h-[140px] flex-1 justify-start gap-2 rounded-3xl border border-[#F3F3F3] bg-white p-[18px]">
      <SkeletonBlock width="70%" height={19} radius={6} />
      <SkeletonBlock width="40%" height={34} radius={8} />
      <SkeletonBlock width={60} height={14} radius={6} />
    </View>
  );
}

/** Skeleton for a VehicleCard. */
export function SkeletonVehicleCard() {
  return (
    <View className="w-[270px] gap-4 rounded-3xl border border-[#F3F3F3] bg-white p-5">
      <View className="flex-row items-center gap-3">
        <SkeletonBlock width={52} height={52} radius={26} />
        <View className="flex-1 gap-2">
          <SkeletonBlock width="70%" height={16} />
          <SkeletonBlock width="35%" height={10} />
        </View>
      </View>
      <SkeletonBlock height={140} radius={16} />
      <View className="gap-2.5">
        <SkeletonBlock height={10} />
        <SkeletonBlock height={10} />
        <SkeletonBlock height={10} />
        <SkeletonBlock width="50%" height={20} radius={10} />
      </View>
    </View>
  );
}

/** Skeleton for a FleetUtilizationCard. */
export function SkeletonFleetCard() {
  return (
    <View className="w-48 items-center gap-3 rounded-2xl bg-white p-4">
      <SkeletonBlock width={72} height={72} radius={36} />
      <SkeletonBlock width="70%" height={14} />
      <SkeletonBlock width="90%" height={10} />
      <SkeletonBlock width="90%" height={10} />
    </View>
  );
}
