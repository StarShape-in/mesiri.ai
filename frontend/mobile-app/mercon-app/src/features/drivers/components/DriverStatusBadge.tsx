import React from 'react';
import { Text, View } from 'react-native';
import type { DriverDisplayStatus } from '../types';

const META: Record<DriverDisplayStatus, { label: string; bg: string; color: string }> = {
  Available: { label: 'Available', bg: '#F0FDF4', color: '#16A34A' },
  OnTrip:    { label: 'On Trip',   bg: '#FFF0EB', color: '#F24822' },
  OffDuty:   { label: 'Offline',   bg: '#F5F5F7', color: '#6E6E80' },
  Inactive:  { label: 'Inactive',  bg: '#F5F5F7', color: '#6E6E80' },
  Suspended: { label: 'Suspended', bg: '#FEF2F2', color: '#DC2626' },
  OnLeave:   { label: 'On Leave',  bg: '#EFF6FF', color: '#2563EB' },
};

interface DriverStatusBadgeProps {
  status: DriverDisplayStatus;
  className?: string;
}

/** Status pill — color is automatic from the driver's status. */
export function DriverStatusBadge({ status, className }: DriverStatusBadgeProps) {
  const { label, bg, color } = META[status];
  return (
    <View style={{ backgroundColor: bg }} className={`self-start rounded-full px-2.5 py-1 ${className ?? ''}`}>
      <Text style={{ color }} className="text-[11px] font-semibold">{label}</Text>
    </View>
  );
}
