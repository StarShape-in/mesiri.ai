import { useCallback, useMemo } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import { customersApi } from '../api/customersApi';
import { sortCustomers, statusFilterToIsActive, toCustomerListItem } from '../services/customersService';
import { useCustomerAggregates } from './useCustomerAggregates';
import type { CustomerListItem, CustomerSortOption, CustomerStatusFilter } from '../types';

const PAGE_SIZE = 20;

export function customersListKey(search: string, status: CustomerStatusFilter) {
  return ['customers', 'list', search, status] as const;
}

interface UseCustomersParams {
  search?: string;
  status?: CustomerStatusFilter;
  sort?: CustomerSortOption;
}

export interface UseCustomersResult {
  customers: CustomerListItem[];
  /** Server-side total for the current search/filter — not the number loaded so far. */
  total: number;
  pagination: { page: number; perPage: number; totalPages: number };
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  isRefreshing: boolean;
  fetchNextPage: () => void;
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
}

/**
 * Backend-paginated customer list with infinite scroll.
 *
 * Search and status filter round-trip to the server (`GET /customers` supports
 * both). Sorting is applied client-side: the controller hard-codes
 * `orderBy: { name: 'asc' }`, and revenue/trip ordering is computed from
 * aggregates the customer table does not hold.
 */
export function useCustomers({
  search = '',
  status = 'all',
  sort = 'name',
}: UseCustomersParams = {}): UseCustomersResult {
  const aggregates = useCustomerAggregates();

  const list = useInfiniteQuery({
    queryKey: customersListKey(search, status),
    queryFn: ({ pageParam }) =>
      customersApi.getCustomers({
        page: pageParam,
        per_page: PAGE_SIZE,
        search,
        is_active: statusFilterToIsActive(status),
      }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) =>
      lastPage.meta.page < lastPage.meta.total_pages ? lastPage.meta.page + 1 : undefined,
  });

  const customers = useMemo(() => {
    const flat = (list.data?.pages ?? []).flatMap((page) =>
      page.data.map((raw) =>
        toCustomerListItem(
          raw,
          aggregates.tripsByCustomer,
          aggregates.invoicesByCustomer,
          aggregates.rateCardsByCustomer,
        ),
      ),
    );
    return sortCustomers(flat, sort);
  }, [list.data, aggregates.tripsByCustomer, aggregates.invoicesByCustomer, aggregates.rateCardsByCustomer, sort]);

  const meta = list.data?.pages[list.data.pages.length - 1]?.meta;

  const refresh = useCallback(async () => {
    await Promise.all([list.refetch(), aggregates.refresh()]);
  }, [list, aggregates]);

  return {
    customers,
    total: list.data?.pages[0]?.meta.total ?? 0,
    pagination: {
      page: meta?.page ?? 1,
      perPage: meta?.per_page ?? PAGE_SIZE,
      totalPages: meta?.total_pages ?? 1,
    },
    // The aggregates only enrich rows — the list is usable before they land.
    loading: list.isLoading,
    error: list.isError ? 'Could not load customers.' : null,
    refresh,
    isRefreshing: list.isRefetching && !list.isFetchingNextPage,
    fetchNextPage: list.fetchNextPage,
    hasNextPage: !!list.hasNextPage,
    isFetchingNextPage: list.isFetchingNextPage,
  };
}
