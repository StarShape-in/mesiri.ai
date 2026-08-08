import { useQuery } from '@tanstack/react-query';
import { driverDetailsApi, type RawDriverTrip } from '../api/driverDetailsApi';

export function driverTripsKey(driverId: string) {
  return ['drivers', 'detail', driverId, 'trips'] as const;
}

/**
 * Every trip belonging to a driver, with vehicle + customer joined.
 *
 * Shared by useDriverPerformance and useDriverAssignment so the two never
 * issue the same request twice — React Query dedupes them on this key.
 */
export function useDriverTrips(driverId: string | undefined) {
  const query = useQuery({
    queryKey: driverTripsKey(driverId ?? ''),
    queryFn: () => driverDetailsApi.getDriverTrips(driverId as string),
    enabled: !!driverId,
    staleTime: 60_000,
  });

  return {
    trips: (query.data ?? []) as RawDriverTrip[],
    loading: query.isLoading,
    error: query.isError ? 'Could not load trips.' : null,
    refresh: query.refetch,
  };
}
