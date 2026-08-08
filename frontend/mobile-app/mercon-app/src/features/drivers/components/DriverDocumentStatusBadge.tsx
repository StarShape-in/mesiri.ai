import React from 'react';
import { Text, View } from 'react-native';
import type { DriverDocumentStatus } from '../types';

/**
 * Distinct from the dashboard's DocumentStatusBadge, which keys purely off
 * days-remaining. A driver document also carries a real `DocStatus`, so
 * "Pending Renewal" (awaiting review) is a state a date alone cannot express.
 */
const META: Record<DriverDocumentStatus, { label: string; bg: string; color: string }> = {
  Valid:          { label: 'Valid',           bg: '#F0FDF4', color: '#16A34A' },
  ExpiresSoon:    { label: 'Expires Soon',    bg: '#FFFBEB', color: '#D97706' },
  Expired:        { label: 'Expired',         bg: '#FEF2F2', color: '#DC2626' },
  PendingRenewal: { label: 'Pending Renewal', bg: '#EFF6FF', color: '#2563EB' },
};

interface DriverDocumentStatusBadgeProps {
  status: DriverDocumentStatus;
  className?: string;
}

export function DriverDocumentStatusBadge({ status, className }: DriverDocumentStatusBadgeProps) {
  const { label, bg, color } = META[status];
  return (
    <View style={{ backgroundColor: bg }} className={`self-start rounded-full px-2.5 py-1 ${className ?? ''}`}>
      <Text numberOfLines={1} style={{ color }} className="text-[11px] font-semibold">
        {label}
      </Text>
    </View>
  );
}
