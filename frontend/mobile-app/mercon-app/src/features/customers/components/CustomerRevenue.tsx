import React from 'react';
import { Text, View } from 'react-native';
import { Colors } from '@/theme/tokens';
import { formatCompactMoney } from '../services/customersService';

interface CustomerRevenueProps {
  tripsThisMonth: number;
  revenue: number;
  outstanding: number;
  currency: string;
}

/**
 * Right-hand figures on a customer card, right-aligned so the numbers line up
 * down the list regardless of name length.
 *
 * Revenue is the sum of the customer's `Paid` invoices; anything billed but
 * unpaid is shown separately as outstanding rather than folded in.
 */
export function CustomerRevenue({ tripsThisMonth, revenue, outstanding, currency }: CustomerRevenueProps) {
  return (
    <View className="items-end">
      <Text numberOfLines={1} className="text-[19px] font-bold leading-[23px] text-gray-900">
        {tripsThisMonth}
      </Text>
      <Text numberOfLines={1} className="text-[10px] font-medium text-gray-400">
        trips this month
      </Text>

      <Text numberOfLines={1} className="mt-2.5 text-[14px] font-bold" style={{ color: Colors.accent }}>
        {formatCompactMoney(revenue, currency)}
      </Text>
      <Text numberOfLines={1} className="text-[10px] font-medium text-gray-400">
        revenue
      </Text>

      {outstanding > 0 && (
        <Text numberOfLines={1} className="mt-1 text-[10px] font-semibold" style={{ color: Colors.warning }}>
          {formatCompactMoney(outstanding, currency)} due
        </Text>
      )}
    </View>
  );
}
