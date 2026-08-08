import React from 'react';
import { Text, View } from 'react-native';

interface DriverTripsProps {
  totalTrips: number | null;
  className?: string;
}

export function DriverTrips({ totalTrips, className }: DriverTripsProps) {
  return (
    <View className={className}>
      <Text className="text-right text-sm font-bold text-gray-900">
        {totalTrips !== null ? totalTrips.toLocaleString() : '—'}
      </Text>
      <Text className="text-right text-[10px] text-gray-400">Trips</Text>
    </View>
  );
}
