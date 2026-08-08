import { useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Polyline, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

import { GeoPoint, PREDEFINED_ROUTES } from '@/services/telemetrySimulator';
import { MAP_THEMES } from '@/components/maps/mapThemes';

// Compact Pickup Marker (Emerald)
const microPickupIcon = L.divIcon({
  html: `<div style="background-color: #10B981; color: white; border-radius: 50%; box-shadow: 0 0 8px rgba(16, 185, 129, 0.8); width: 16px; height: 16px; border: 2px solid white;"></div>`,
  className: '',
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});

// Compact Dropoff Marker (Crimson)
const microDropoffIcon = L.divIcon({
  html: `<div style="background-color: #F43F5E; color: white; border-radius: 50%; box-shadow: 0 0 8px rgba(244, 63, 94, 0.8); width: 16px; height: 16px; border: 2px solid white;"></div>`,
  className: '',
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});

function createMicroTruckIcon(heading: number) {
  return L.divIcon({
    html: `
      <div style="position: relative; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center;">
        <div style="width: 20px; height: 20px; border-radius: 50%; background: #0F1017; color: #FF5500; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 10px rgba(255, 85, 0, 0.9); border: 1.5px solid #FF5500; transform: rotate(${heading}deg); transition: transform 0.3s ease;">
          <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polygon points="3 11 22 2 13 21 11 13 3 11"/></svg>
        </div>
      </div>
    `,
    className: '',
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  });
}

function MapFlyTo({ lat, lng }: { lat: number; lng: number }) {
  const map = useMap();
  useEffect(() => {
    map.flyTo([lat, lng], map.getZoom(), { animate: true });
  }, [lat, lng, map]);
  return null;
}

interface TripMicroMapProps {
  currentLat: number;
  currentLng: number;
  heading: number;
  pickupCoords: GeoPoint;
  dropoffCoords: GeoPoint;
  routeKey?: string;
  themeId?: string;
}

export default function TripMicroMap({
  currentLat,
  currentLng,
  heading,
  pickupCoords,
  dropoffCoords,
  routeKey = 'riyadh-jeddah',
  themeId = 'voyager',
}: TripMicroMapProps) {
  const currentTheme = MAP_THEMES[themeId] || MAP_THEMES.voyager;

  const routeDef = PREDEFINED_ROUTES[routeKey];
  const polylineWaypoints = routeDef
    ? routeDef.waypoints.map((w) => [w.lat, w.lng] as [number, number])
    : [
        [pickupCoords.lat, pickupCoords.lng] as [number, number],
        [dropoffCoords.lat, dropoffCoords.lng] as [number, number],
      ];

  return (
    <div className="h-[120px] w-full rounded-xl overflow-hidden relative z-0 border border-black/[0.08] pointer-events-none select-none" style={{ background: currentTheme.previewColor }}>
      <MapContainer
        center={[currentLat, currentLng]}
        zoom={6.5}
        scrollWheelZoom={false}
        dragging={false}
        touchZoom={false}
        doubleClickZoom={false}
        boxZoom={false}
        keyboard={false}
        zoomControl={false}
        attributionControl={false}
        style={{ height: '100%', width: '100%', zIndex: 0 }}
      >
        <TileLayer url={currentTheme.url} />
        <MapFlyTo lat={currentLat} lng={currentLng} />

        <Polyline
          positions={polylineWaypoints}
          pathOptions={{ color: '#FF5500', weight: 3, opacity: 0.85, dashArray: '4, 6' }}
        />

        <Marker position={[pickupCoords.lat, pickupCoords.lng]} icon={microPickupIcon} />
        <Marker position={[dropoffCoords.lat, dropoffCoords.lng]} icon={microDropoffIcon} />
        <Marker position={[currentLat, currentLng]} icon={createMicroTruckIcon(heading)} />
      </MapContainer>
    </div>
  );
}
