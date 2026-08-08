import React from 'react';
import { Text, View } from 'react-native';
import { SortDropdown } from '@/shared/components';
import { CUSTOMER_SORT_OPTIONS } from '../hooks/useCustomerSorting';
import type { CustomerSortOption } from '../types';

interface CustomerListHeaderProps {
  /** Server-side total for the active search/filter. */
  total: number;
  sort: CustomerSortOption;
  onSortChange: (sort: CustomerSortOption) => void;
}

/** "All Customers (18)" on the left, sort control on the right. */
export function CustomerListHeader({ total, sort, onSortChange }: CustomerListHeaderProps) {
  return (
    <View className="flex-row items-center justify-between gap-3">
      <Text numberOfLines={1} className="flex-1 text-[15px] font-bold text-gray-900">
        All Customers ({total})
      </Text>
      <SortDropdown value={sort} options={CUSTOMER_SORT_OPTIONS} onChange={onSortChange} />
    </View>
  );
}
