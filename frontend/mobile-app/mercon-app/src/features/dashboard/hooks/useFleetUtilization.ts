import { useQuery } from '@tanstack/react-query';
import { dashboardApi } from '../api/dashboardApi';
import { buildFleetUtilization, periodRange } from '../services/dashboardService';
import type { FleetPeriod } from '../types';

export function fleetUtilizationKey(period: FleetPeriod) {
  return ['dashboard', 'fleet-utilization', period] as const;
}

export function useFleetUtilization(period: FleetPeriod) {
  return useQuery({
    queryKey: fleetUtilizationKey(period),
    queryFn: async () => {
      const range = periodRange(period);
      const [vehicles, tripCounts] = await Promise.all([
        dashboardApi.getVehicles(),
        dashboardApi.getFleetTripCounts(range),
      ]);
      return buildFleetUtilization(vehicles, tripCounts);
    },
  });
}
