import { useMemo } from 'react';
import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { driversApi } from '../api/driversApi';
import { sortDrivers, toDriverListItem, tripCountMap } from '../services/driversService';
import type { DriverSortOption, DriverStatus } from '../types';

const PAGE_SIZE = 20;

interface UseDriversParams {
  search?: string;
  status?: DriverStatus | null;
  sort?: DriverSortOption;
}

/** Paginated (infinite-scroll) driver list — search/status reload from the backend, sort is applied client-side (see driversService.sortDrivers). */
export function useDrivers({ search = '', status = null, sort = 'name' }: UseDriversParams) {
  const tripCounts = useQuery({
    queryKey: ['drivers', 'trip-counts'],
    queryFn: driversApi.getDriverTripCounts,
    staleTime: 5 * 60_000,
  });
  const tripCountById = useMemo(() => tripCountMap(tripCounts.data ?? []), [tripCounts.data]);

  const list = useInfiniteQuery({
    queryKey: ['drivers', 'list', search, status],
    queryFn: ({ pageParam }) => driversApi.getDrivers({ page: pageParam, per_page: PAGE_SIZE, search, status }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => (lastPage.meta.page < lastPage.meta.total_pages ? lastPage.meta.page + 1 : undefined),
  });

  const drivers = useMemo(() => {
    const flat = (list.data?.pages ?? []).flatMap((page) => page.data.map((raw) => toDriverListItem(raw, tripCountById)));
    return sortDrivers(flat, sort);
  }, [list.data, tripCountById, sort]);

  return {
    drivers,
    total: list.data?.pages[0]?.meta.total ?? 0,
    loading: list.isLoading,
    error: list.isError ? 'Could not load drivers.' : null,
    refresh: list.refetch,
    isRefreshing: list.isRefetching && !list.isFetchingNextPage,
    fetchNextPage: list.fetchNextPage,
    hasNextPage: !!list.hasNextPage,
    isFetchingNextPage: list.isFetchingNextPage,
  };
}
