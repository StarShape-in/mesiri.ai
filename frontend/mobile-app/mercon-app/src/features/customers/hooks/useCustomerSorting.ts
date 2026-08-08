import { useState } from 'react';
import type { SortOption } from '@/shared/components';
import type { CustomerSortOption } from '../types';

/**
 * "Contract Expiry" is deliberately absent: rate cards carry no validity
 * dates in the schema, so there would be nothing real to order by.
 */
export const CUSTOMER_SORT_OPTIONS: readonly SortOption<CustomerSortOption>[] = [
  { value: 'name', label: 'Name (A–Z)' },
  { value: 'revenue', label: 'Highest Revenue' },
  { value: 'trips', label: 'Most Trips' },
  { value: 'newest', label: 'Newest' },
  { value: 'recent', label: 'Recently Active' },
];

export function useCustomerSorting(initial: CustomerSortOption = 'name') {
  const [sort, setSort] = useState<CustomerSortOption>(initial);
  return { sort, setSort, options: CUSTOMER_SORT_OPTIONS };
}
