import React from 'react';
import { ActivityIndicator, Text, View } from 'react-native';

interface LoadingOverlayProps {
  visible: boolean;
  label?: string;
}

export function LoadingOverlay({ visible, label }: LoadingOverlayProps) {
  if (!visible) return null;
  return (
    <View
      pointerEvents="auto"
      className="absolute inset-0 z-50 items-center justify-center gap-2 bg-white/70"
    >
      <ActivityIndicator color="#E8450F" size="large" />
      {label ? <Text className="text-sm font-medium text-gray-600">{label}</Text> : null}
    </View>
  );
}
