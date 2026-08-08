import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Navigation, Gauge, ShieldCheck } from 'lucide-react';

import { PREDEFINED_ROUTES, GeoPoint } from '@/services/telemetrySimulator';
import { useSimulatedTelemetry } from '@/hooks/useSimulatedTelemetry';
import { MAP_THEMES } from '@/components/maps/mapThemes';
import MapThemeSelector from '@/components/maps/MapThemeSelector';

// Shadcn UI components
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';

// High-Tech Neon Pickup Marker (Emerald LED)
const pickupMarkerIcon = L.divIcon({
  html: `
    <div style="position: relative; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;">
      <div class="animate-ping" style="position: absolute; width: 30px; height: 30px; border-radius: 50%; background-color: rgba(16, 185, 129, 0.4);"></div>
      <div style="width: 26px; height: 26px; border-radius: 50%; background: #0F1017; color: #10B981; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 16px rgba(16, 185, 129, 0.8); border: 2px solid #10B981; z-index: 2;">
        <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>
      </div>
    </div>
  `,
  className: '',
  iconSize: [32, 32],
  iconAnchor: [16, 16],
});

// High-Tech Neon Dropoff Marker (Crimson LED)
const dropoffMarkerIcon = L.divIcon({
  html: `
    <div style="position: relative; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;">
      <div class="animate-ping" style="position: absolute; width: 30px; height: 30px; border-radius: 50%; background-color: rgba(244, 63, 94, 0.4);"></div>
      <div style="width: 26px; height: 26px; border-radius: 50%; background: #0F1017; color: #F43F5E; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 16px rgba(244, 63, 94, 0.8); border: 2px solid #F43F5E; z-index: 2;">
        <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>
      </div>
    </div>
  `,
  className: '',
  iconSize: [32, 32],
  iconAnchor: [16, 16],
});

function createLiveTruckIcon(heading: number) {
  return L.divIcon({
    html: `
      <div style="position: relative; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center;">
        <div class="animate-ping" style="position: absolute; width: 40px; height: 40px; border-radius: 50%; background-color: rgba(255, 85, 0, 0.4);"></div>
        <div style="width: 30px; height: 30px; border-radius: 50%; background: #0F1017; color: #FF5500; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 20px rgba(255, 85, 0, 0.9), inset 0 0 8px #FF5500; border: 2px solid #FF5500; transform: rotate(${heading}deg); transition: transform 0.3s ease;">
          <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"><polygon points="3 11 22 2 13 21 11 13 3 11"/></svg>
        </div>
      </div>
    `,
    className: '',
    iconSize: [40, 40],
    iconAnchor: [20, 20],
  });
}

function MapFlyTo({ lat, lng }: { lat: number; lng: number }) {
  const map = useMap();
  useEffect(() => {
    map.flyTo([lat, lng], map.getZoom(), { animate: true });
  }, [lat, lng, map]);
  return null;
}

interface TripLiveMapCardProps {
  tripId: string;
  refId: string;
  pickupLat?: number;
  pickupLng?: number;
  dropoffLat?: number;
  dropoffLng?: number;
}

export default function TripLiveMapCard({
  tripId,
  refId,
  pickupLat = 24.6432,
  pickupLng = 46.7214,
  dropoffLat = 21.5433,
  dropoffLng = 39.1728,
}: TripLiveMapCardProps) {
  const navigate = useNavigate();
  const { fleet } = useSimulatedTelemetry(1);
  const [mapThemeId, setMapThemeId] = useState<string>('voyager');

  const currentTheme = MAP_THEMES[mapThemeId] || MAP_THEMES.voyager;
  const simulatedTruck = fleet.find((f) => f.tripId === tripId || f.refId === refId) || fleet[0];

  const pickupPoint: GeoPoint = { lat: pickupLat, lng: pickupLng };
  const dropoffPoint: GeoPoint = { lat: dropoffLat, lng: dropoffLng };

  const route = PREDEFINED_ROUTES['riyadh-jeddah'];
  const polylineWaypoints = route
    ? route.waypoints.map((w) => [w.lat, w.lng] as [number, number])
    : [
        [pickupPoint.lat, pickupPoint.lng] as [number, number],
        [dropoffPoint.lat, dropoffPoint.lng] as [number, number],
      ];

  const currentLat = simulatedTruck ? simulatedTruck.currentCoords.lat : pickupLat;
  const currentLng = simulatedTruck ? simulatedTruck.currentCoords.lng : pickupLng;
  const speed = simulatedTruck ? simulatedTruck.speedKmH : 88;
  const heading = simulatedTruck ? simulatedTruck.heading : 240;
  const progress = simulatedTruck ? simulatedTruck.progressPercentage : 42;
  const etaMin = simulatedTruck ? simulatedTruck.etaMinutes : 320;

  return (
    <Card className="border-black/[0.06] shadow-md rounded-2xl bg-white overflow-hidden">
      <CardHeader className="pb-3 border-b border-black/[0.04]">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[#FF5500] animate-ping" />
              <CardTitle className="text-sm font-extrabold text-[#111]">Live Trip Route Tracking</CardTitle>
              <Badge variant="outline" className={`text-[10px] font-mono ${currentTheme.badgeColor}`}>
                {currentTheme.name}
              </Badge>
            </div>
            <CardDescription className="text-xs text-[#6E6E80] mt-0.5">
              Live GPS telemetry positioning along Expressway Route 40
            </CardDescription>
          </div>

          <div className="flex items-center gap-2">
            {/* Map Theme Dropdown Selector */}
            <MapThemeSelector
              currentThemeId={mapThemeId}
              onThemeChange={(newTheme) => setMapThemeId(newTheme)}
            />

            <Button
              size="sm"
              variant="outline"
              onClick={() => navigate(`/trips/${tripId}/track`)}
              className="h-8 text-xs font-bold gap-1 border-black/[0.08] hover:bg-[#F5F5F7]"
            >
              <Navigation size={13} className="text-[#FF5500]" />
              <span>Full Radar</span>
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-4 space-y-3">
        {/* Map View */}
        <div className="h-[310px] rounded-xl overflow-hidden border border-black/[0.1] relative z-0 shadow-xl" style={{ background: currentTheme.previewColor }}>
          <MapContainer
            center={[currentLat, currentLng]}
            zoom={8}
            scrollWheelZoom={true}
            style={{ height: '100%', width: '100%', zIndex: 0 }}
          >
            <TileLayer
              key={currentTheme.id}
              attribution={currentTheme.attribution}
              url={currentTheme.url}
            />

            <MapFlyTo lat={currentLat} lng={currentLng} />

            <Polyline
              positions={polylineWaypoints}
              pathOptions={{ color: '#FF5500', weight: 4, opacity: 0.85, dashArray: '6, 10' }}
            />

            <Marker position={[pickupPoint.lat, pickupPoint.lng]} icon={pickupMarkerIcon}>
              <Popup className={currentTheme.isDark ? "dark-map-popup" : ""}>
                <div className="text-xs font-sans p-1">
                  <p className="font-bold text-[#10B981]">Pickup Terminal</p>
                  <p className="text-[10px] text-gray-500">Riyadh Dry Port</p>
                </div>
              </Popup>
            </Marker>

            <Marker position={[dropoffPoint.lat, dropoffPoint.lng]} icon={dropoffMarkerIcon}>
              <Popup className={currentTheme.isDark ? "dark-map-popup" : ""}>
                <div className="text-xs font-sans p-1">
                  <p className="font-bold text-[#F43F5E]">Dropoff Terminal</p>
                  <p className="text-[10px] text-gray-500">Jeddah Islamic Port</p>
                </div>
              </Popup>
            </Marker>

            <Marker
              position={[currentLat, currentLng]}
              icon={createLiveTruckIcon(heading)}
            >
              <Popup className={currentTheme.isDark ? "dark-map-popup" : ""}>
                <div className="text-xs font-sans p-1">
                  <p className="font-bold text-[#FF5500]">{simulatedTruck.plateNumber}</p>
                  <p className="text-[10px] text-gray-500">Speed: {speed} km/h</p>
                </div>
              </Popup>
            </Marker>
          </MapContainer>

          {/* Bottom Telemetry Bar */}
          <div className={`absolute bottom-3 left-3 right-3 z-[400] p-3.5 rounded-xl shadow-xl border text-xs space-y-2 ${
            currentTheme.isDark 
              ? 'bg-[#090A0F]/90 backdrop-blur-xl border-white/10 text-white' 
              : 'bg-white/95 backdrop-blur-xl border-black/[0.08] text-[#111]'
          }`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="bg-[#FF5500]/20 p-2 rounded-lg text-[#FF5500] border border-[#FF5500]/30">
                  <Gauge size={18} />
                </div>
                <div>
                  <p className="text-[9px] text-gray-400 font-mono uppercase tracking-wider">Telemetry Stream</p>
                  <p className="text-xs font-bold">
                    {speed} km/h • <span className="font-mono text-[11px] text-orange-500">{currentLat.toFixed(4)}, {currentLng.toFixed(4)}</span>
                  </p>
                </div>
              </div>

              <div className="text-right">
                <p className="text-[9px] text-gray-400 font-mono uppercase tracking-wider">Progress / ETA</p>
                <p className="text-xs font-bold text-[#FF5500]">
                  {progress}% • ~{Math.floor(etaMin / 60)}h {etaMin % 60}m
                </p>
              </div>
            </div>

            <Progress value={progress} className="h-1.5 bg-gray-200 dark:bg-white/10" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
