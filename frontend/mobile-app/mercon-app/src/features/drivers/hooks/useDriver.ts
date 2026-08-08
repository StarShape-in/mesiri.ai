import { useCallback, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { driverDetailsApi } from '../api/driverDetailsApi';
import { toDriverDetail } from '../services/driverDetailsService';
import { useDriverAssignment } from './useDriverAssignment';
import { useDriverDocuments } from './useDriverDocuments';
import { useDriverPerformance } from './useDriverPerformance';
import type {
  AssignedVehicle,
  DriverAssignment,
  DriverDetail,
  DriverDocument,
  DriverPerformance,
} from '../types';

export function driverDetailKey(driverId: string) {
  return ['drivers', 'detail', driverId] as const;
}

export interface UseDriverResult {
  driver: DriverDetail | null;
  vehicle: AssignedVehicle | null;
  documents: DriverDocument[];
  documentsNeedingAttention: number;
  /** Section-local state so the documents card can load/fail without taking the screen down. */
  documentsLoading: boolean;
  documentsError: string | null;
  performance: DriverPerformance;
  assignment: DriverAssignment | null;
  /** True only on the very first load — a pull-to-refresh does not re-trigger the skeleton. */
  loading: boolean;
  /** True while a pull-to-refresh is in flight. */
  refreshing: boolean;
  /** Non-null only when the driver record itself failed; section errors stay local to their card. */
  error: string | null;
  /** Whether the driver id resolved to nothing (404) — the screen renders an EmptyState for this. */
  notFound: boolean;
  refresh: () => Promise<void>;
}

/**
 * Single entry point for the Driver Details screen.
 *
 * Composes the section hooks rather than re-fetching: useDriverPerformance and
 * useDriverAssignment both read the same cached trip list, so the screen
 * issues three requests (driver, documents, trips) plus one for the active
 * trip's stops — not one per section.
 */
export function useDriver(driverId: string | undefined): UseDriverResult {
  const driverQuery = useQuery({
    queryKey: driverDetailKey(driverId ?? ''),
    queryFn: () => driverDetailsApi.getDriver(driverId as string),
    enabled: !!driverId,
    // A driver's status changes while an operator watches this screen.
    refetchInterval: 60_000,
  });

  const driver = useMemo(
    () => (driverQuery.data ? toDriverDetail(driverQuery.data) : null),
    [driverQuery.data],
  );

  const documents = useDriverDocuments(driverId);
  const performance = useDriverPerformance(driverId, driver?.aiRiskScore ?? null);
  const assignment = useDriverAssignment(driverId);

  const refresh = useCallback(async () => {
    await Promise.all([
      driverQuery.refetch(),
      documents.refresh(),
      performance.refresh(),
    ]);
    // Stops depend on which trip is active, so refresh them after the trip list settles.
    assignment.refresh();
  }, [driverQuery, documents, performance, assignment]);

  const status = (driverQuery.error as { response?: { status?: number } } | null)?.response?.status;

  return {
    driver,
    vehicle: assignment.vehicle,
    documents: documents.documents,
    documentsNeedingAttention: documents.needsAttention,
    documentsLoading: documents.loading,
    documentsError: documents.error,
    performance: performance.performance,
    assignment: assignment.assignment,
    loading: driverQuery.isLoading,
    refreshing: driverQuery.isRefetching,
    error: driverQuery.isError && status !== 404 ? 'Could not load this driver.' : null,
    notFound: status === 404,
    refresh,
  };
}
