import React from 'react';
import { Text, View } from 'react-native';
import type { VehicleCardStatus } from '../types';

const STATUS_COLORS: Record<VehicleCardStatus, { bg: string; color: string }> = {
  'En Route':    { bg: '#EFF6FF', color: '#2563EB' },
  'Loading':     { bg: '#F5F3FF', color: '#7C3AED' },
  'Idle':        { bg: '#F5F5F7', color: '#6E6E80' },
  'Maintenance': { bg: '#FFFBEB', color: '#D97706' },
  'Delivered':   { bg: '#F0FDF4', color: '#16A34A' },
  'Offline':     { bg: '#EBEBED', color: '#9898A4' },
  'Delayed':     { bg: '#FEF2F2', color: '#DC2626' },
};

interface StatusBadgeProps {
  status: VehicleCardStatus;
  className?: string;
}

/** Vehicle-card status pill — pass one of the seven `VehicleCardStatus` values; color is automatic. */
export function StatusBadge({ status, className }: StatusBadgeProps) {
  const { bg, color } = STATUS_COLORS[status];
  return (
    <View style={{ backgroundColor: bg }} className={`self-start rounded-full px-2.5 py-1 ${className ?? ''}`}>
      <Text style={{ color }} className="text-[11px] font-semibold">{status}</Text>
    </View>
  );
}
