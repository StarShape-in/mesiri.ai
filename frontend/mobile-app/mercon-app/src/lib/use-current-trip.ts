import { useCallback, useEffect, useState } from 'react';
import { tripService, type MobileTrip } from './trips';
import { getApiErrorMessage } from './api';

let cachedTrip: MobileTrip | null = null;
let isFetched = false;

/** Loads the driver's current active trip. Uses in-memory caching to eliminate tab-switch flickering. */
export function useCurrentTrip() {
  const [trip, setTrip] = useState<MobileTrip | null>(cachedTrip);
  const [loading, setLoading] = useState(!isFetched);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async (opts?: { showLoading?: boolean } | any) => {
    const showLoading = typeof opts === 'boolean' ? opts : typeof opts?.showLoading === 'boolean' ? opts.showLoading : !isFetched;
    if (showLoading) setLoading(true);
    setError(null);
    try {
      const data = await tripService.getCurrent();
      cachedTrip = data;
      isFetched = true;
      setTrip(data);
    } catch (e) {
      setError(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refetch(); }, [refetch]);

  return { trip, loading, error, refetch, setTrip };
}
