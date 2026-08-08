import React from 'react';
import { Text, TextInput, TouchableOpacity, View } from 'react-native';
import { Plus, Search, SlidersHorizontal, X } from 'lucide-react-native';
import { IconButton } from '@/features/dashboard/components';
import { Colors } from '@/theme/tokens';
import { CUSTOMER_STATUS_FILTERS } from '../hooks/useCustomerFilters';
import type { CustomerStatusFilter } from '../types';

interface CustomersHeaderProps {
  searchVisible: boolean;
  onToggleSearch: () => void;
  query: string;
  onQueryChange: (value: string) => void;

  filtersVisible: boolean;
  onToggleFilters: () => void;
  status: CustomerStatusFilter;
  onStatusChange: (status: CustomerStatusFilter) => void;

  /** Hidden entirely when the signed-in role cannot create customers. */
  canCreate: boolean;
  onAddCustomer: () => void;
}

/**
 * Fixed page header: title + subtitle, search/filter icon buttons, an
 * expanding search field, status chips, and the Add Customer action.
 */
export function CustomersHeader({
  searchVisible,
  onToggleSearch,
  query,
  onQueryChange,
  filtersVisible,
  onToggleFilters,
  status,
  onStatusChange,
  canCreate,
  onAddCustomer,
}: CustomersHeaderProps) {
  return (
    <View className="border-b border-gray-100 bg-white px-4 pb-4 pt-3">
      <View className="flex-row items-start justify-between">
        <View className="min-w-0 flex-1 pr-3">
          <Text numberOfLines={1} className="text-[26px] font-extrabold leading-[30px] text-gray-900">
            Customers
          </Text>
          <Text numberOfLines={1} className="mt-1 text-[13px] text-gray-500">
            Manage your customers and contracts
          </Text>
        </View>
        <View className="flex-row gap-2.5">
          <IconButton Icon={Search} onPress={onToggleSearch} elevated />
          <IconButton Icon={SlidersHorizontal} onPress={onToggleFilters} badge={status !== 'all'} elevated />
        </View>
      </View>

      {searchVisible && (
        <View className="mt-4 flex-row items-center rounded-2xl border border-gray-200 bg-gray-50 px-3.5">
          <Search size={16} color={Colors.gray400} strokeWidth={2} />
          <TextInput
            value={query}
            onChangeText={onQueryChange}
            placeholder="Search customers by name"
            placeholderTextColor={Colors.gray400}
            autoFocus
            returnKeyType="search"
            className="h-11 flex-1 px-2.5 text-[14px] text-gray-900"
          />
          {query.length > 0 && (
            <TouchableOpacity onPress={() => onQueryChange('')} hitSlop={10} accessibilityLabel="Clear search">
              <X size={15} color={Colors.gray400} strokeWidth={2.5} />
            </TouchableOpacity>
          )}
        </View>
      )}

      {filtersVisible && (
        <View className="mt-4 flex-row" style={{ gap: 8 }}>
          {CUSTOMER_STATUS_FILTERS.map((f) => {
            const active = f.value === status;
            return (
              <TouchableOpacity
                key={f.value}
                onPress={() => onStatusChange(f.value)}
                activeOpacity={0.8}
                accessibilityRole="button"
                accessibilityState={{ selected: active }}
                style={active ? { backgroundColor: Colors.accent, borderColor: Colors.accent } : undefined}
                className={`rounded-full border px-3.5 py-1.5 ${active ? '' : 'border-gray-200 bg-white'}`}
              >
                <Text className={`text-xs font-semibold ${active ? 'text-white' : 'text-gray-600'}`}>
                  {f.label}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>
      )}

      {canCreate && (
        <TouchableOpacity
          onPress={onAddCustomer}
          activeOpacity={0.85}
          accessibilityRole="button"
          accessibilityLabel="Add customer"
          style={{ borderColor: Colors.accent }}
          className="mt-4 h-11 flex-row items-center justify-center rounded-2xl border bg-white"
        >
          <Plus size={16} color={Colors.accent} strokeWidth={2.5} />
          <Text style={{ color: Colors.accent }} className="ml-1.5 text-[14px] font-bold">
            Add Customer
          </Text>
        </TouchableOpacity>
      )}
    </View>
  );
}
