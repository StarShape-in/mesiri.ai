import { useMemo } from 'react';
import { useDriverTrips } from './useDriverTrips';
import { computeDriverPerformance } from '../services/driverDetailsService';
import type { DriverPerformance } from '../types';

export interface UseDriverPerformanceResult {
  performance: DriverPerformance;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

const EMPTY: DriverPerformance = {
  totalTrips: 0,
  completedTrips: 0,
  onTimeRatePct: null,
  onTimeSample: 0,
  aiRiskScore: null,
  averageRating: null,
};

/**
 * All-time performance for one driver, computed from their real trips.
 *
 * Deliberately not sourced from GET /reports/drivers: that endpoint returns
 * only `total_trips` / `completed_trips` / `ai_risk_score` — it drops the
 * planned-vs-actual timestamps, so an on-time rate cannot be derived from it.
 * The per-driver trip list carries those timestamps, so the figures here are
 * real rather than approximated.
 *
 * @param aiRiskScore The driver's `ai_risk_score`, which lives on the driver
 *                    record rather than on their trips.
 */
export function useDriverPerformance(
  driverId: string | undefined,
  aiRiskScore: number | null = null,
): UseDriverPerformanceResult {
  const { trips, loading, error, refresh } = useDriverTrips(driverId);

  const performance = useMemo(
    () => (trips.length === 0 && loading ? EMPTY : computeDriverPerformance(trips, aiRiskScore)),
    [trips, loading, aiRiskScore],
  );

  return { performance, loading, error, refresh };
}
