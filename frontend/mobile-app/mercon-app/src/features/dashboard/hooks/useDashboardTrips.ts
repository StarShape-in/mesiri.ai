/**
 * Shared trip-list query behind useActiveTrips / useDelayedDeliveries /
 * useActiveVehicles — one network call, three different `select` views over
 * it (React Query dedupes by queryKey+queryFn).
 */
import { useQuery } from '@tanstack/react-query';
import { dashboardApi } from '../api/dashboardApi';
import { buildActiveVehicleCards, filterActiveTrips, filterDelayedDeliveries } from '../services/dashboardService';

export const dashboardTripsKey = ['dashboard', 'trips'] as const;

function useDashboardTripsQuery<T>(select: (trips: Awaited<ReturnType<typeof dashboardApi.getTrips>>) => T) {
  return useQuery({
    queryKey: dashboardTripsKey,
    queryFn: () => dashboardApi.getTrips({ per_page: 100 }),
    select,
  });
}

export function useActiveTrips() {
  return useDashboardTripsQuery(filterActiveTrips);
}

export function useDelayedDeliveries() {
  return useDashboardTripsQuery(filterDelayedDeliveries);
}

export function useActiveVehicles() {
  return useDashboardTripsQuery(buildActiveVehicleCards);
}
