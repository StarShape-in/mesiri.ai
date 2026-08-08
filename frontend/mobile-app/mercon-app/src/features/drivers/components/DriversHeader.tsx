import React from 'react';
import { Text, View } from 'react-native';
import { SearchButton } from './SearchButton';
import { FilterButton } from './FilterButton';

interface DriversHeaderProps {
  onSearchPress?: () => void;
  onFilterPress?: () => void;
  filterActive?: boolean;
  className?: string;
}

/** Fixed (non-scrolling) page header: title + subtitle on the left, search/filter icon buttons on the right. */
export function DriversHeader({ onSearchPress, onFilterPress, filterActive, className }: DriversHeaderProps) {
  return (
    <View className={`flex-row items-center justify-between border-b border-gray-100 bg-white px-4 pb-4 pt-3 ${className ?? ''}`}>
      <View className="gap-1">
        <Text className="text-[26px] font-extrabold leading-[30px] text-gray-900">Drivers</Text>
        <Text className="text-[13px] text-gray-500">Manage and monitor your fleet drivers</Text>
      </View>
      <View className="flex-row gap-2.5">
        <SearchButton onPress={onSearchPress} />
        <FilterButton onPress={onFilterPress} active={filterActive} />
      </View>
    </View>
  );
}
