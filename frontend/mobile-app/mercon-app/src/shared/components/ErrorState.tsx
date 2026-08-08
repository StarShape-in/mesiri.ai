import React from 'react';
import { Text, TouchableOpacity, View } from 'react-native';
import { TriangleAlert } from 'lucide-react-native';

interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
  className?: string;
}

export function ErrorState({ message, onRetry, retryLabel = 'Try again', className }: ErrorStateProps) {
  return (
    <View className={`items-center gap-3 py-8 px-4 ${className ?? ''}`}>
      <TriangleAlert size={28} color="#DC2626" strokeWidth={2} />
      <Text className="text-center text-sm text-gray-600">{message}</Text>
      {onRetry && (
        <TouchableOpacity onPress={onRetry} activeOpacity={0.8} className="rounded-full bg-primary px-5 py-2">
          <Text className="text-sm font-semibold text-white">{retryLabel}</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}
