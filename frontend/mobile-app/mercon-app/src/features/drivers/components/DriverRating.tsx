import React from 'react';
import { Text, View } from 'react-native';
import { Star } from 'lucide-react-native';

interface DriverRatingProps {
  /** Null renders "—" — the backend has no rating field today, this is never fabricated. */
  rating: number | null;
  className?: string;
}

export function DriverRating({ rating, className }: DriverRatingProps) {
  return (
    <View className={`flex-row items-center gap-1 ${className ?? ''}`}>
      <Star size={13} color="#F24822" fill="#F24822" strokeWidth={0} />
      <Text className="text-sm font-bold text-gray-900">{rating !== null ? rating.toFixed(1) : '—'}</Text>
    </View>
  );
}
