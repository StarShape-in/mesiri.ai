export interface GeoPoint {
  lat: number;
  lng: number;
}

export interface RouteWaypoint extends GeoPoint {
  name: string;
}

export interface RouteDefinition {
  id: string;
  name: string;
  origin: string;
  destination: string;
  waypoints: GeoPoint[];
  totalDistanceKm: number;
  estimatedDurationHours: number;
}

export interface SimulatedTruckTelemetry {
  tripId: string;
  refId: string;
  driverName: string;
  driverPhone: string;
  plateNumber: string;
  assetType: string;
  cargoType: string;
  status: 'InTransit' | 'AtPickup' | 'AtDelivery' | 'Idle' | 'Completed';
  originName: string;
  destinationName: string;
  pickupCoords: GeoPoint;
  dropoffCoords: GeoPoint;
  currentCoords: GeoPoint;
  heading: number; // Bearing angle in degrees 0-360
  speedKmH: number;
  progressPercentage: number; // 0 to 100
  distanceCompletedKm: number;
  distanceRemainingKm: number;
  etaMinutes: number;
}

// Key Saudi Arabian Logistics Corridors & Waypoints
export const PREDEFINED_ROUTES: Record<string, RouteDefinition> = {
  'riyadh-jeddah': {
    id: 'riyadh-jeddah',
    name: 'Riyadh to Jeddah Highway Expressway (Route 40)',
    origin: 'Riyadh Dry Port & Logistics Park',
    destination: 'Jeddah Islamic Port Terminal 1',
    totalDistanceKm: 950,
    estimatedDurationHours: 10.5,
    waypoints: [
      { lat: 24.6432, lng: 46.7214 }, // Riyadh Port
      { lat: 24.5800, lng: 46.2100 }, // Muzahmiyya
      { lat: 24.1500, lng: 45.2800 }, // Quwayiyya
      { lat: 23.4000, lng: 44.4000 }, // Halaban
      { lat: 22.8200, lng: 42.9200 }, // Zalim
      { lat: 22.3800, lng: 41.5100 }, // Radwan
      { lat: 21.6500, lng: 40.4000 }, // Taif Bypass
      { lat: 21.4200, lng: 39.8200 }, // Mecca Outer Ring
      { lat: 21.5433, lng: 39.1728 }, // Jeddah Port
    ],
  },
  'dammam-riyadh': {
    id: 'dammam-riyadh',
    name: 'King Fahd Highway (Dammam to Riyadh - Route 85)',
    origin: 'King Abdulaziz Port Dammam',
    destination: 'Riyadh Industrial City 2',
    totalDistanceKm: 410,
    estimatedDurationHours: 4.5,
    waypoints: [
      { lat: 26.4350, lng: 50.1040 }, // Dammam Port
      { lat: 26.3100, lng: 49.9800 }, // Khobar Outer
      { lat: 25.9200, lng: 49.3700 }, // Hofuf Bypass
      { lat: 25.5500, lng: 48.0000 }, // Judah Oasis
      { lat: 25.1800, lng: 47.1500 }, // Rumah
      { lat: 24.7800, lng: 46.8500 }, // Riyadh Industrial 2
    ],
  },
  'medina-mecca': {
    id: 'medina-mecca',
    name: 'Haramain Highway (Medina to Mecca - Route 15)',
    origin: 'Medina Central Distribution Hub',
    destination: 'Mecca Southern Freight Depot',
    totalDistanceKm: 420,
    estimatedDurationHours: 4.8,
    waypoints: [
      { lat: 24.4672, lng: 39.6112 }, // Medina
      { lat: 23.8500, lng: 39.3200 }, // Wadi Al-Yatima
      { lat: 23.1200, lng: 39.2100 }, // Badr Junction
      { lat: 22.4000, lng: 39.1000 }, // Rabigh Industrial
      { lat: 21.8000, lng: 39.3000 }, // Usfan
      { lat: 21.3891, lng: 39.8579 }, // Mecca Depot
    ],
  },
  'riyadh-tabuk': {
    id: 'riyadh-tabuk',
    name: 'Northern Transport Corridor (Riyadh to Tabuk)',
    origin: 'Riyadh Northern Hub',
    destination: 'Tabuk Logistics Station',
    totalDistanceKm: 1250,
    estimatedDurationHours: 13.0,
    waypoints: [
      { lat: 24.7136, lng: 46.6753 }, // Riyadh
      { lat: 26.3500, lng: 43.9700 }, // Buraidah (Qassim)
      { lat: 27.5200, lng: 41.6900 }, // Hail
      { lat: 28.3800, lng: 36.5600 }, // Tabuk
    ],
  },
};

/** Calculate distance between two GPS lat/lng points in KM */
export function calculateHaversineDistance(p1: GeoPoint, p2: GeoPoint): number {
  const R = 6371; // Earth's radius in km
  const dLat = ((p2.lat - p1.lat) * Math.PI) / 180;
  const dLng = ((p2.lng - p1.lng) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((p1.lat * Math.PI) / 180) *
      Math.cos((p2.lat * Math.PI) / 180) *
      Math.sin(dLng / 2) *
      Math.sin(dLng / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

/** Calculate bearing angle in degrees (0-360) between two GPS points */
export function calculateBearing(p1: GeoPoint, p2: GeoPoint): number {
  const lat1 = (p1.lat * Math.PI) / 180;
  const lat2 = (p2.lat * Math.PI) / 180;
  const dLng = ((p2.lng - p1.lng) * Math.PI) / 180;

  const y = Math.sin(dLng) * Math.cos(lat2);
  const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLng);
  const brng = (Math.atan2(y, x) * 180) / Math.PI;
  return (brng + 360) % 360;
}

/** Interpolate position along polyline waypoints based on progress percentage (0 - 100) */
export function interpolateRoutePosition(
  waypoints: GeoPoint[],
  progressPercent: number
): { coords: GeoPoint; heading: number } {
  if (!waypoints || waypoints.length === 0) {
    return { coords: { lat: 24.7136, lng: 46.6753 }, heading: 0 };
  }
  if (waypoints.length === 1 || progressPercent <= 0) {
    const heading = waypoints.length > 1 ? calculateBearing(waypoints[0], waypoints[1]) : 0;
    return { coords: waypoints[0], heading };
  }
  if (progressPercent >= 100) {
    const lastIdx = waypoints.length - 1;
    const heading = calculateBearing(waypoints[lastIdx - 1], waypoints[lastIdx]);
    return { coords: waypoints[lastIdx], heading };
  }

  // Calculate total route segment lengths
  const segmentDistances: number[] = [];
  let totalDist = 0;
  for (let i = 0; i < waypoints.length - 1; i++) {
    const d = calculateHaversineDistance(waypoints[i], waypoints[i + 1]);
    segmentDistances.push(d);
    totalDist += d;
  }

  const targetDistance = (progressPercent / 100) * totalDist;
  let accumulatedDist = 0;

  for (let i = 0; i < segmentDistances.length; i++) {
    const segDist = segmentDistances[i];
    if (accumulatedDist + segDist >= targetDistance || i === segmentDistances.length - 1) {
      const segProgress = segDist > 0 ? (targetDistance - accumulatedDist) / segDist : 0;
      const clampedSegProgress = Math.max(0, Math.min(1, segProgress));

      const p1 = waypoints[i];
      const p2 = waypoints[i + 1];

      const lat = p1.lat + (p2.lat - p1.lat) * clampedSegProgress;
      const lng = p1.lng + (p2.lng - p1.lng) * clampedSegProgress;
      const heading = calculateBearing(p1, p2);

      return { coords: { lat, lng }, heading };
    }
    accumulatedDist += segDist;
  }

  return { coords: waypoints[waypoints.length - 1], heading: 0 };
}

// Initial Mock Active Fleet Data across Saudi Arabia
export const MOCK_SIMULATED_FLEET: SimulatedTruckTelemetry[] = [
  {
    tripId: 'trp-001',
    refId: 'TRP-8921',
    driverName: 'Mohammed Al-Otaibi',
    driverPhone: '+966 50 123 4567',
    plateNumber: '7842-KSA',
    assetType: 'Reefer Trailer (40ft)',
    cargoType: 'Pharmaceutical Frozen Goods',
    status: 'InTransit',
    originName: 'Riyadh Dry Port',
    destinationName: 'Jeddah Port Terminal 1',
    pickupCoords: PREDEFINED_ROUTES['riyadh-jeddah'].waypoints[0],
    dropoffCoords: PREDEFINED_ROUTES['riyadh-jeddah'].waypoints[PREDEFINED_ROUTES['riyadh-jeddah'].waypoints.length - 1],
    currentCoords: PREDEFINED_ROUTES['riyadh-jeddah'].waypoints[3],
    heading: 240,
    speedKmH: 88,
    progressPercentage: 42,
    distanceCompletedKm: 399,
    distanceRemainingKm: 551,
    etaMinutes: 375,
  },
  {
    tripId: 'trp-002',
    refId: 'TRP-8922',
    driverName: 'Tariq Al-Ghamdi',
    driverPhone: '+966 54 987 6543',
    plateNumber: '4109-KSA',
    assetType: 'Flatbed Heavy Hauler',
    cargoType: 'Structural Steel Beams',
    status: 'InTransit',
    originName: 'Dammam Port Depot',
    destinationName: 'Riyadh Industrial 2',
    pickupCoords: PREDEFINED_ROUTES['dammam-riyadh'].waypoints[0],
    dropoffCoords: PREDEFINED_ROUTES['dammam-riyadh'].waypoints[PREDEFINED_ROUTES['dammam-riyadh'].waypoints.length - 1],
    currentCoords: PREDEFINED_ROUTES['dammam-riyadh'].waypoints[2],
    heading: 250,
    speedKmH: 94,
    progressPercentage: 65,
    distanceCompletedKm: 266,
    distanceRemainingKm: 144,
    etaMinutes: 92,
  },
  {
    tripId: 'trp-003',
    refId: 'TRP-8923',
    driverName: 'Khaled Al-Dawsari',
    driverPhone: '+966 56 333 2211',
    plateNumber: '9921-KSA',
    assetType: 'Dry Container Semi-Trailer',
    cargoType: 'FMCG Retail Cartons',
    status: 'AtPickup',
    originName: 'Medina Distribution Hub',
    destinationName: 'Mecca Southern Depot',
    pickupCoords: PREDEFINED_ROUTES['medina-mecca'].waypoints[0],
    dropoffCoords: PREDEFINED_ROUTES['medina-mecca'].waypoints[PREDEFINED_ROUTES['medina-mecca'].waypoints.length - 1],
    currentCoords: PREDEFINED_ROUTES['medina-mecca'].waypoints[0],
    heading: 180,
    speedKmH: 0,
    progressPercentage: 5,
    distanceCompletedKm: 21,
    distanceRemainingKm: 399,
    etaMinutes: 280,
  },
  {
    tripId: 'trp-004',
    refId: 'TRP-8924',
    driverName: 'Fahad Al-Harbi',
    driverPhone: '+966 55 444 8899',
    plateNumber: '3312-KSA',
    assetType: 'Liquid Fuel Tanker',
    cargoType: 'Diesel Fuel Cargo',
    status: 'InTransit',
    originName: 'Riyadh Logistics Depot',
    destinationName: 'Tabuk Freight Hub',
    pickupCoords: PREDEFINED_ROUTES['riyadh-tabuk'].waypoints[0],
    dropoffCoords: PREDEFINED_ROUTES['riyadh-tabuk'].waypoints[PREDEFINED_ROUTES['riyadh-tabuk'].waypoints.length - 1],
    currentCoords: PREDEFINED_ROUTES['riyadh-tabuk'].waypoints[1],
    heading: 320,
    speedKmH: 90,
    progressPercentage: 28,
    distanceCompletedKm: 350,
    distanceRemainingKm: 900,
    etaMinutes: 600,
  },
  {
    tripId: 'trp-005',
    refId: 'TRP-8925',
    driverName: 'Sultan Al-Shammari',
    driverPhone: '+966 59 777 1122',
    plateNumber: '1188-KSA',
    assetType: 'Box Truck (10 Ton)',
    cargoType: 'Electronics & Spare Parts',
    status: 'Idle',
    originName: 'Riyadh Ring Road Service Area',
    destinationName: 'Riyadh Depot',
    pickupCoords: { lat: 24.7500, lng: 46.7100 },
    dropoffCoords: { lat: 24.7136, lng: 46.6753 },
    currentCoords: { lat: 24.7500, lng: 46.7100 },
    heading: 0,
    speedKmH: 0,
    progressPercentage: 0,
    distanceCompletedKm: 0,
    distanceRemainingKm: 15,
    etaMinutes: 0,
  },
];
