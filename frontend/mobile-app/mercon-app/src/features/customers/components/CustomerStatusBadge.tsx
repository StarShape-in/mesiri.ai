import React from 'react';
import { Text, View } from 'react-native';
import type { CustomerDisplayStatus } from '../types';

/**
 * Only `Active` and `Inactive` are ever produced from real data — the schema
 * has a single `isActive` boolean. The other three are mapped so the badge is
 * ready if a status column is added, without this feature emitting them.
 */
const META: Record<CustomerDisplayStatus, { label: string; bg: string; color: string }> = {
  Active:          { label: 'Active',           bg: '#F0FDF4', color: '#16A34A' },
  Inactive:        { label: 'Inactive',         bg: '#F5F5F7', color: '#6E6E80' },
  OnHold:          { label: 'On Hold',          bg: '#FFFBEB', color: '#D97706' },
  ContractExpired: { label: 'Contract Expired', bg: '#FEF2F2', color: '#DC2626' },
  Cancelled:       { label: 'Cancelled',        bg: '#FEF2F2', color: '#DC2626' },
};

interface CustomerStatusBadgeProps {
  status: CustomerDisplayStatus;
  className?: string;
}

export function CustomerStatusBadge({ status, className }: CustomerStatusBadgeProps) {
  const { label, bg, color } = META[status];
  return (
    <View style={{ backgroundColor: bg }} className={`self-start rounded-full px-2 py-0.5 ${className ?? ''}`}>
      <Text numberOfLines={1} style={{ color }} className="text-[10px] font-bold">
        {label}
      </Text>
    </View>
  );
}
