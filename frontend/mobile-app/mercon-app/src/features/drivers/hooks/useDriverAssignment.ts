import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { driverDetailsApi } from '../api/driverDetailsApi';
import { findActiveTrip, toDriverAssignment } from '../services/driverDetailsService';
import { useDriverTrips } from './useDriverTrips';
import type { AssignedVehicle, DriverAssignment } from '../types';

export function tripStopsKey(tripId: string) {
  return ['trips', 'detail', tripId, 'stops'] as const;
}

export interface UseDriverAssignmentResult {
  /** Null when the driver has no trip in an active state. */
  assignment: DriverAssignment | null;
  /**
   * The vehicle on the active trip. A driver has no direct vehicle relation
   * in the schema, so this is null whenever they are not on a trip — the
   * Assigned Vehicle card hides itself in that case.
   */
  vehicle: AssignedVehicle | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

/**
 * The driver's current assignment.
 *
 * Two-step by necessity: GET /trips?driver_id= returns the trip with its
 * vehicle and customer but *not* its stops, and GET /trips/:id is the only
 * endpoint that returns stops. The card renders from the first response and
 * fills pickup/dropoff in when the second resolves, so it never blocks on the
 * follow-up request.
 */
export function useDriverAssignment(driverId: string | undefined): UseDriverAssignmentResult {
  const { trips, loading: tripsLoading, error: tripsError, refresh: refreshTrips } = useDriverTrips(driverId);

  const activeTrip = useMemo(() => findActiveTrip(trips), [trips]);

  const stopsQuery = useQuery({
    queryKey: tripStopsKey(activeTrip?.id ?? ''),
    queryFn: () => driverDetailsApi.getTripDetail(activeTrip?.id as string),
    enabled: !!activeTrip?.id,
    staleTime: 60_000,
  });

  const assignment = useMemo(
    () => (activeTrip ? toDriverAssignment(activeTrip, stopsQuery.data) : null),
    [activeTrip, stopsQuery.data],
  );

  return {
    assignment,
    vehicle: assignment?.vehicle ?? null,
    loading: tripsLoading,
    error: tripsError,
    refresh: () => {
      refreshTrips();
      if (activeTrip?.id) stopsQuery.refetch();
    },
  };
}
