import React from 'react';
import { Text, View } from 'react-native';

const COLORS = {
  valid:        { bg: '#F0FDF4', color: '#16A34A' },
  expiringSoon: { bg: '#FFFBEB', color: '#D97706' },
  expired:      { bg: '#FEF2F2', color: '#DC2626' },
};

function labelFor(daysLeft: number): { label: string; tone: keyof typeof COLORS } {
  if (daysLeft < 0) return { label: 'Expired', tone: 'expired' };
  if (daysLeft === 0) return { label: 'Expires Today', tone: 'expiringSoon' };
  if (daysLeft <= 30) return { label: `${daysLeft} ${daysLeft === 1 ? 'Day' : 'Days'} Left`, tone: 'expiringSoon' };
  return { label: 'Valid', tone: 'valid' };
}

interface DocumentStatusBadgeProps {
  daysLeft: number;
  className?: string;
}

/** Pill showing "Expired" / "Expires Today" / "N Days Left" / "Valid" — color is automatic from days remaining. */
export function DocumentStatusBadge({ daysLeft, className }: DocumentStatusBadgeProps) {
  const { label, tone } = labelFor(daysLeft);
  const { bg, color } = COLORS[tone];
  return (
    <View style={{ backgroundColor: bg }} className={`self-start rounded-full px-2.5 py-1 ${className ?? ''}`}>
      <Text numberOfLines={1} style={{ color }} className="text-[11px] font-semibold">{label}</Text>
    </View>
  );
}
