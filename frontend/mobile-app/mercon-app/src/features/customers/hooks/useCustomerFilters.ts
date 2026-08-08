import { useState } from 'react';
import type { CustomerStatusFilter } from '../types';

export const CUSTOMER_STATUS_FILTERS: { value: CustomerStatusFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' },
];

/**
 * Status filter state. Only Active/Inactive exist — the backend tracks a
 * single `isActive` boolean and `GET /customers` filters on it server-side.
 */
export function useCustomerFilters(initial: CustomerStatusFilter = 'all') {
  const [status, setStatus] = useState<CustomerStatusFilter>(initial);

  return {
    status,
    setStatus,
    isFiltered: status !== 'all',
    reset: () => setStatus('all'),
  };
}
