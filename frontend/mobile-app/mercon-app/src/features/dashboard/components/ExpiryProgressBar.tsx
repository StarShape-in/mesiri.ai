import React from 'react';
import { View } from 'react-native';

const LOOKBACK_DAYS = 60;

interface ExpiryProgressBarProps {
  daysLeft: number;
  className?: string;
}

/** Thin bar showing how close a document is to expiring — green (>30d), orange (<=30d), red (expired or <7d). */
export function ExpiryProgressBar({ daysLeft, className }: ExpiryProgressBarProps) {
  const fraction = Math.max(0, Math.min(1, 1 - daysLeft / LOOKBACK_DAYS));
  const color = daysLeft < 0 || daysLeft < 7 ? '#DC2626' : daysLeft <= 30 ? '#D97706' : '#16A34A';

  return (
    <View className={`h-1 w-full overflow-hidden rounded-full bg-gray-100 ${className ?? ''}`}>
      <View style={{ width: `${fraction * 100}%`, backgroundColor: color }} className="h-full rounded-full" />
    </View>
  );
}
