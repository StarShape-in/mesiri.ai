import React from 'react';
import { Text, TouchableOpacity, View } from 'react-native';
import { Plus } from 'lucide-react-native';
import { Colors } from '@/theme/tokens';

interface CustomerActionsProps {
  onViewDetails: () => void;
  onCreateTrip: () => void;
}

/** Two equal-width buttons: outlined secondary, filled primary. */
export function CustomerActions({ onViewDetails, onCreateTrip }: CustomerActionsProps) {
  return (
    <View className="flex-row" style={{ gap: 10 }}>
      <TouchableOpacity
        onPress={onViewDetails}
        activeOpacity={0.85}
        accessibilityRole="button"
        accessibilityLabel="View customer details"
        className="h-11 flex-1 items-center justify-center rounded-2xl border border-gray-200 bg-white"
      >
        <Text className="text-[13px] font-bold text-gray-900">View Details</Text>
      </TouchableOpacity>

      <TouchableOpacity
        onPress={onCreateTrip}
        activeOpacity={0.85}
        accessibilityRole="button"
        accessibilityLabel="Create trip for this customer"
        style={{ backgroundColor: Colors.accent }}
        className="h-11 flex-1 flex-row items-center justify-center rounded-2xl"
      >
        <Plus size={15} color={Colors.white} strokeWidth={2.5} />
        <Text className="ml-1.5 text-[13px] font-bold text-white">Create Trip</Text>
      </TouchableOpacity>
    </View>
  );
}
