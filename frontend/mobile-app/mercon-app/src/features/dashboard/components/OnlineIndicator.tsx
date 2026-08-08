import React from 'react';
import { View } from 'react-native';

interface OnlineIndicatorProps {
  online: boolean;
  size?: number;
  /** White ring around the dot — on for badge-over-avatar use, off for standalone (e.g. next to a "Online" label). */
  ring?: boolean;
  className?: string;
}

export function OnlineIndicator({ online, size = 10, ring = true, className }: OnlineIndicatorProps) {
  return (
    <View
      style={{ width: size, height: size, borderRadius: size / 2 }}
      className={`${ring ? 'border-2 border-white' : ''} ${online ? 'bg-success' : 'bg-gray-300'} ${className ?? ''}`}
    />
  );
}
