/**
 * Streams the driver's GPS to the server while a trip is active (foreground).
 * Requests location permission, watches position (~10s / 20m), and emits
 * 'driver:location_update' over the shared socket. Stops when the trip ends
 * or the component unmounts. Background tracking is a later hardening step.
 */
import { useEffect, useRef } from 'react';
import * as Location from 'expo-location';
import { getSocket } from './socket';
import type { MobileTrip } from './trips';

const UPDATE_INTERVAL_MS = 10_000;
const MIN_DISTANCE_M = 20;

export function useLiveTracking(trip: MobileTrip | null, driverId: string | null | undefined) {
  const subRef = useRef<Location.LocationSubscription | null>(null);
  const tripId = trip?.id ?? null;

  useEffect(() => {
    let cancelled = false;

    async function start() {
      if (!tripId || !driverId) return;
      const perm = await Location.requestForegroundPermissionsAsync();
      if (!perm.granted || cancelled) return;

      const socket = await getSocket();
      if (cancelled) return;
      const sub = await Location.watchPositionAsync(
        {
          accuracy: Location.Accuracy.Balanced,
          timeInterval: UPDATE_INTERVAL_MS,
          distanceInterval: MIN_DISTANCE_M,
        },
        (loc) => {
          socket.emit('driver:location_update', {
            tripId,
            driverId,
            lat: loc.coords.latitude,
            lng: loc.coords.longitude,
            speed: loc.coords.speed ?? 0,
          });
        },
      );

      if (cancelled) sub.remove();
      else subRef.current = sub;
    }

    start().catch(() => {});

    return () => {
      cancelled = true;
      subRef.current?.remove();
      subRef.current = null;
    };
  }, [tripId, driverId]);
}
