/**
 * Lightweight, illustrative route preview — not a real map yet. Renders an
 * origin marker, a curved route line, and a truck marker at `progress`
 * along it, over a flat "map" background.
 *
 * The props (origin/destination labels + progress) are the stable contract:
 * swapping this out for a live Google Maps / Mapbox view later shouldn't
 * require any change to VehicleCard, which only passes these props through.
 */
import React from 'react';
import { Text, View } from 'react-native';
import Svg, { Circle, Path } from 'react-native-svg';
import { Truck } from 'lucide-react-native';

interface RoutePreviewProps {
  originLabel: string;
  destinationLabel: string;
  /** 0-1 position of the truck marker along the route. */
  progress?: number;
  height?: number;
  className?: string;
}

// Logical coordinate space the route curve is drawn in — the SVG scales this to fill the container.
const VIEW_WIDTH = 300;
const VIEW_HEIGHT = 140;
const ORIGIN = { x: 28, y: 104 };
const CONTROL = { x: 150, y: 14 };
const DESTINATION = { x: 272, y: 52 };

function pointOnQuadraticBezier(t: number) {
  const oneMinusT = 1 - t;
  const x = oneMinusT * oneMinusT * ORIGIN.x + 2 * oneMinusT * t * CONTROL.x + t * t * DESTINATION.x;
  const y = oneMinusT * oneMinusT * ORIGIN.y + 2 * oneMinusT * t * CONTROL.y + t * t * DESTINATION.y;
  return { x, y };
}

export function RoutePreview({ originLabel, destinationLabel, progress = 0.5, height = 140, className }: RoutePreviewProps) {
  const clampedProgress = Math.max(0.05, Math.min(0.95, progress));
  const truckPoint = pointOnQuadraticBezier(clampedProgress);
  const truckLeftPct = (truckPoint.x / VIEW_WIDTH) * 100;
  const truckTopPct = (truckPoint.y / VIEW_HEIGHT) * 100;

  return (
    <View
      style={{ height }}
      className={`w-full overflow-hidden rounded-2xl bg-[#F2F3F5] ${className ?? ''}`}
    >
      <Svg width="100%" height="100%" viewBox={`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`} preserveAspectRatio="none">
        <Path
          d={`M${ORIGIN.x},${ORIGIN.y} Q${CONTROL.x},${CONTROL.y} ${DESTINATION.x},${DESTINATION.y}`}
          stroke="#C4C7CE"
          strokeWidth={2.5}
          strokeDasharray="1 7"
          strokeLinecap="round"
          fill="none"
        />
        {/* Origin marker */}
        <Circle cx={ORIGIN.x} cy={ORIGIN.y} r={6} fill="#E8450F" stroke="#FFFFFF" strokeWidth={2} />
        {/* Destination marker */}
        <Circle cx={DESTINATION.x} cy={DESTINATION.y} r={7} fill="#FFFFFF" stroke="#1C1C2E" strokeWidth={2} />
        <Circle cx={DESTINATION.x} cy={DESTINATION.y} r={2.5} fill="#1C1C2E" />
      </Svg>

      {/* Truck marker, positioned along the curve */}
      <View
        pointerEvents="none"
        style={{ position: 'absolute', left: `${truckLeftPct}%`, top: `${truckTopPct}%`, marginLeft: -12, marginTop: -12 }}
        className="h-6 w-6 items-center justify-center rounded-full bg-white"
      >
        <Truck size={13} color="#E8450F" strokeWidth={2.4} />
      </View>

      {/* Labels */}
      <Text numberOfLines={1} className="absolute left-2.5 top-2 max-w-[45%] text-[10px] font-semibold text-gray-500">
        {originLabel}
      </Text>
      <Text numberOfLines={1} className="absolute bottom-2 right-2.5 max-w-[45%] text-right text-[10px] font-semibold text-navbg">
        {destinationLabel}
      </Text>
    </View>
  );
}
