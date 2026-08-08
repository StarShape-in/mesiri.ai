import React from 'react';
import { View } from 'react-native';
import { Navigation, Phone, User } from 'lucide-react-native';
import { DriverActionButton } from './DriverActionButton';

interface DriverActionGroupProps {
  /** Swaps "Call" for "Track" once the driver is out on a trip. */
  onTrip: boolean;
  canCall: boolean;
  onCall?: () => void;
  onTrack?: () => void;
  onView?: () => void;
  className?: string;
}

/** Full-width row of action buttons: Call/View normally, Track/View while the driver is on a trip. */
export function DriverActionGroup({ onTrip, canCall, onCall, onTrack, onView, className }: DriverActionGroupProps) {
  return (
    <View className={`flex-row gap-2.5 ${className ?? ''}`}>
      {onTrip ? (
        <DriverActionButton label="Track" Icon={Navigation} onPress={onTrack} className="flex-1" />
      ) : (
        <DriverActionButton label="Call" Icon={Phone} onPress={onCall} disabled={!canCall} className="flex-1" />
      )}
      <DriverActionButton label="View" Icon={User} onPress={onView} className="flex-1" />
    </View>
  );
}
