import { useCallback, useEffect, useState } from 'react';
import { tripService, type MobileTrip } from './trips';
import { getApiErrorMessage } from './api';

let cachedHistory: MobileTrip[] = [];
let isHistoryFetched = false;

/** Loads the driver's past trips. Uses in-memory caching to eliminate tab-switch flickering. */
export function useTripHistory() {
  const [trips, setTrips] = useState<MobileTrip[]>(cachedHistory);
  const [loading, setLoading] = useState(!isHistoryFetched);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async (opts?: { showLoading?: boolean } | any) => {
    const showLoading = typeof opts === 'boolean' ? opts : typeof opts?.showLoading === 'boolean' ? opts.showLoading : !isHistoryFetched;
    if (showLoading) setLoading(true);
    setError(null);
    try {
      const data = await tripService.getHistory();
      cachedHistory = data;
      isHistoryFetched = true;
      setTrips(data);
    } catch (e) {
      setError(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refetch(); }, [refetch]);

  return { trips, loading, error, refetch };
}
