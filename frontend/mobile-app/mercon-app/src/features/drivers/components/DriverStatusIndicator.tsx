import React from 'react';
import { View } from 'react-native';
import type { DriverDisplayStatus } from '../types';

const COLORS: Record<DriverDisplayStatus, string> = {
  Available: '#16A34A', // online — green
  OnTrip: '#F24822',    // orange
  OffDuty: '#9898A4',   // offline — grey
  Inactive: '#DC2626',  // unavailable — red
  Suspended: '#DC2626',
  OnLeave: '#2563EB',
};

interface DriverStatusIndicatorProps {
  status: DriverDisplayStatus;
  size?: number;
  className?: string;
}

/** Bottom-right dot on DriverAvatar — green (online) / orange (on trip) / grey (offline) / red (unavailable). */
export function DriverStatusIndicator({ status, size = 14, className }: DriverStatusIndicatorProps) {
  return (
    <View
      style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: COLORS[status] }}
      className={`border-2 border-white ${className ?? ''}`}
    />
  );
}
