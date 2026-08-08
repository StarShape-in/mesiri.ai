import React from 'react';
import { Text, View } from 'react-native';
import { SortDropdown } from './SortDropdown';
import type { DriverSortOption } from '../types';

interface DriversListHeaderProps {
  total: number;
  sort: DriverSortOption;
  onSortChange: (sort: DriverSortOption) => void;
  className?: string;
}

export function DriversListHeader({ total, sort, onSortChange, className }: DriversListHeaderProps) {
  return (
    <View className={`flex-row items-center justify-between ${className ?? ''}`}>
      <Text className="text-base font-bold text-gray-900">All Drivers ({total})</Text>
      <SortDropdown value={sort} onChange={onSortChange} />
    </View>
  );
}
