import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { driversApi } from '../api/driversApi';
import { computeDriverStats } from '../services/driversService';

/** Fleet-wide driver counts (independent of the list's current search/filter), for the DriverStatCard row. */
export function useDriverStats() {
  const query = useQuery({
    queryKey: ['drivers', 'stats'],
    queryFn: () => driversApi.getDrivers({ page: 1, per_page: 200 }),
  });

  const stats = useMemo(() => computeDriverStats(query.data?.data ?? []), [query.data]);

  return {
    ...stats,
    loading: query.isLoading,
    error: query.isError ? 'Could not load driver stats.' : null,
    refresh: query.refetch,
  };
}
