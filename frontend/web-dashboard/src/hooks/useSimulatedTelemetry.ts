import { useState, useEffect, useRef, useCallback } from 'react';
import {
  SimulatedTruckTelemetry,
  MOCK_SIMULATED_FLEET,
  PREDEFINED_ROUTES,
  interpolateRoutePosition,
} from '@/services/telemetrySimulator';

export function useSimulatedTelemetry(initialSpeedMultiplier: number = 1) {
  const [fleet, setFleet] = useState<SimulatedTruckTelemetry[]>(MOCK_SIMULATED_FLEET);
  const [isPlaying, setIsPlaying] = useState<boolean>(true);
  const [speedMultiplier, setSpeedMultiplier] = useState<number>(initialSpeedMultiplier);
  const animFrameRef = useRef<number | null>(null);

  const togglePlay = useCallback(() => {
    setIsPlaying((prev) => !prev);
  }, []);

  const changeSpeedMultiplier = useCallback((multiplier: number) => {
    setSpeedMultiplier(multiplier);
  }, []);

  useEffect(() => {
    if (!isPlaying) {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      return;
    }

    let lastTime = performance.now();

    const tick = (now: number) => {
      const deltaSec = (now - lastTime) / 1000;
      lastTime = now;

      setFleet((prevFleet) =>
        prevFleet.map((truck) => {
          if (truck.status === 'Idle' || truck.status === 'Completed') {
            return truck;
          }

          // Advance progress percentage
          // Normal speed ~ 0.05% per second at 1x
          const increment = 0.05 * speedMultiplier * deltaSec;
          let newProgress = truck.progressPercentage + increment;

          let newStatus: SimulatedTruckTelemetry['status'] = truck.status;
          if (newProgress >= 100) {
            newProgress = 100;
            newStatus = 'Completed';
          }

          // Match pre-defined route or default to riyadh-jeddah
          let routeKey = 'riyadh-jeddah';
          if (truck.refId === 'TRP-8922') routeKey = 'dammam-riyadh';
          if (truck.refId === 'TRP-8923') routeKey = 'medina-mecca';
          if (truck.refId === 'TRP-8924') routeKey = 'riyadh-tabuk';

          const route = PREDEFINED_ROUTES[routeKey];
          const waypoints = route ? route.waypoints : [truck.pickupCoords, truck.dropoffCoords];

          const { coords, heading } = interpolateRoutePosition(waypoints, newProgress);

          const totalDist = route ? route.totalDistanceKm : 900;
          const completedDist = Math.round((newProgress / 100) * totalDist);
          const remainingDist = Math.max(0, totalDist - completedDist);

          // Calculate dynamic speed variation
          const baseSpeed = truck.status === 'InTransit' ? 88 : 0;
          const speedFluc = Math.sin(now / 1000 + parseInt(truck.tripId, 36) || 0) * 4;
          const currentSpeed = newStatus === 'Completed' || newStatus === 'AtPickup' ? 0 : Math.round(baseSpeed + speedFluc);

          const eta = currentSpeed > 0 ? Math.round((remainingDist / currentSpeed) * 60) : 0;

          return {
            ...truck,
            currentCoords: coords,
            heading,
            speedKmH: currentSpeed,
            progressPercentage: Math.round(newProgress * 10) / 10,
            distanceCompletedKm: completedDist,
            distanceRemainingKm: remainingDist,
            etaMinutes: eta,
            status: newStatus,
          };
        })
      );

      animFrameRef.current = requestAnimationFrame(tick);
    };

    animFrameRef.current = requestAnimationFrame(tick);

    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, [isPlaying, speedMultiplier]);

  return {
    fleet,
    isPlaying,
    speedMultiplier,
    togglePlay,
    changeSpeedMultiplier,
  };
}
