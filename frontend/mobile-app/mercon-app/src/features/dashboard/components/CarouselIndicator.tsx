import React from 'react';
import { View } from 'react-native';

interface CarouselIndicatorProps {
  count: number;
  activeIndex: number;
  className?: string;
}

export function CarouselIndicator({ count, activeIndex, className }: CarouselIndicatorProps) {
  if (count <= 1) return null;
  return (
    <View className={`flex-row items-center justify-center gap-1.5 ${className ?? ''}`}>
      {Array.from({ length: count }).map((_, i) => (
        <View
          key={i}
          className={`h-1.5 rounded-full ${i === activeIndex ? 'w-4 bg-primary' : 'w-1.5 bg-gray-300'}`}
        />
      ))}
    </View>
  );
}
