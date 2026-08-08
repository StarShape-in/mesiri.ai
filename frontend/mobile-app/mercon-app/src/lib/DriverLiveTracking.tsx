/**
 * Headless component: streams the driver's GPS while they have an active trip.
 * Rendered once on the driver landing so it keeps running as they move between
 * screens. Polls the current trip so tracking starts/stops as trips are
 * assigned or completed without a manual refresh.
 */
import { useEffect } from 'react';
import { useAuth } from './auth-context';
import { useCurrentTrip } from './use-current-trip';
import { useLiveTracking } from './use-live-tracking';

export function DriverLiveTracking() {
  const { profile } = useAuth();
  const { trip, refetch } = useCurrentTrip();

  useEffect(() => {
    const t = setInterval(refetch, 30_000);
    return () => clearInterval(t);
  }, [refetch]);

  useLiveTracking(trip, profile?.id ?? null);
  return null;
}
