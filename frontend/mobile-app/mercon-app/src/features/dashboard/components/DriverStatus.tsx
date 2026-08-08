import React from 'react';
import { Text, View } from 'react-native';
import { OnlineIndicator } from './OnlineIndicator';

interface DriverStatusProps {
  online: boolean;
  className?: string;
}

/** Small dot + label pair showing a driver's live availability — derived from `Driver.status` (`OnTrip` = online). */
export function DriverStatus({ online, className }: DriverStatusProps) {
  return (
    <View className={`flex-row items-center gap-1.5 ${className ?? ''}`}>
      <OnlineIndicator online={online} size={7} ring={false} />
      <Text className={`text-xs font-medium ${online ? 'text-success' : 'text-gray-400'}`}>
        {online ? 'Online' : 'Offline'}
      </Text>
    </View>
  );
}
