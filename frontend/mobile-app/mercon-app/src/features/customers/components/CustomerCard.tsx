import React from 'react';
import { Text, View } from 'react-native';
import { CustomerLogo } from './CustomerLogo';
import { CustomerStatusBadge } from './CustomerStatusBadge';
import { CustomerInfoGrid } from './CustomerInfoGrid';
import { CustomerRevenue } from './CustomerRevenue';
import { CustomerActions } from './CustomerActions';
import { CustomerOverflowMenu } from './CustomerOverflowMenu';
import type { CustomerListItem, CustomerPermissions } from '../types';

interface CustomerCardProps {
  customer: CustomerListItem;
  permissions: CustomerPermissions;
  onViewDetails: (customer: CustomerListItem) => void;
  onCreateTrip: (customer: CustomerListItem) => void;
  onEdit: (customer: CustomerListItem) => void;
  onToggleActive: (customer: CustomerListItem) => void;
  onDelete: (customer: CustomerListItem) => void;
}

/** Large white card: identity + figures on top, commercial facts, then actions. */
export function CustomerCard({
  customer,
  permissions,
  onViewDetails,
  onCreateTrip,
  onEdit,
  onToggleActive,
  onDelete,
}: CustomerCardProps) {
  return (
    <View
      style={{
        padding: 20,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 8 },
        shadowOpacity: 0.06,
        shadowRadius: 20,
        elevation: 3,
      }}
      className="rounded-3xl border border-[#F3F3F3] bg-white"
    >
      <View className="flex-row items-start">
        <CustomerLogo name={customer.name} size={48} />

        {/* min-w-0 lets long company names truncate instead of shoving the figures off-card. */}
        <View className="min-w-0 flex-1 px-3">
          <Text numberOfLines={1} className="text-[16px] font-bold leading-[20px] text-gray-900">
            {customer.name}
          </Text>
          <Text numberOfLines={1} className="mt-0.5 text-[12px] text-gray-400">
            {customer.phone}
          </Text>
          <View className="mt-1.5">
            <CustomerStatusBadge status={customer.status} />
          </View>
        </View>

        <View className="items-end">
          <CustomerOverflowMenu
            customer={customer}
            permissions={permissions}
            onEdit={() => onEdit(customer)}
            onToggleActive={() => onToggleActive(customer)}
            onDelete={() => onDelete(customer)}
          />
          <View className="mt-1">
            <CustomerRevenue
              tripsThisMonth={customer.tripsThisMonth}
              revenue={customer.revenue}
              outstanding={customer.outstanding}
              currency={customer.currency}
            />
          </View>
        </View>
      </View>

      <View className="my-4 h-px bg-[#F3F3F3]" />

      <CustomerInfoGrid customer={customer} />

      <View className="mt-5">
        <CustomerActions
          onViewDetails={() => onViewDetails(customer)}
          onCreateTrip={() => onCreateTrip(customer)}
        />
      </View>
    </View>
  );
}
