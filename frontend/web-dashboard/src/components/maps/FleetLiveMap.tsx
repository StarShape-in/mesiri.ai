import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { 
  Play, Pause, FastForward, Search, Navigation, 
  ExternalLink, ShieldCheck, Gauge, Activity,
  Map, Table2, Radio
} from 'lucide-react';

import { SimulatedTruckTelemetry } from '@/services/telemetrySimulator';
import { useSimulatedTelemetry } from '@/hooks/useSimulatedTelemetry';
import { MAP_THEMES } from '@/components/maps/mapThemes';
import MapThemeSelector from '@/components/maps/MapThemeSelector';

// Shadcn UI components
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from '@/components/ui/tooltip';
import { Progress } from '@/components/ui/progress';
import { Table, TableHeader, TableBody, TableHead, TableRow, TableCell } from '@/components/ui/table';
import StatusBadge from '@/components/ui/StatusBadge';

// High-Tech Vehicle Marker Generator
function createNeonTruckDivIcon(truck: SimulatedTruckTelemetry, isDarkTheme: boolean) {
  let color = '#FF5500'; // Neon Orange
  let glowColor = 'rgba(255, 85, 0, 0.7)';
  
  if (truck.status === 'AtPickup') {
    color = '#0088FF'; // Neon Blue
    glowColor = 'rgba(0, 136, 255, 0.7)';
  } else if (truck.status === 'Idle') {
    color = '#64748B'; // Slate
    glowColor = 'rgba(100, 116, 139, 0.4)';
  } else if (truck.status === 'Completed') {
    color = '#10B981'; // Neon Emerald
    glowColor = 'rgba(16, 185, 129, 0.7)';
  }

  const bgPod = isDarkTheme ? '#0F1017' : '#FFFFFF';
  const textPlate = isDarkTheme ? '#FFFFFF' : '#1E293B';

  const svgIconHtml = `
    <div style="position: relative; width: 46px; height: 46px; display: flex; align-items: center; justify-content: center;">
      <!-- Neon Radial Pulsing Aura -->
      ${truck.status === 'InTransit' ? `<div class="animate-ping" style="position: absolute; width: 44px; height: 44px; border-radius: 50%; background-color: ${glowColor}; opacity: 0.4;"></div>` : ''}
      
      <!-- Directional Radar Headlamp Arc -->
      <div style="position: absolute; width: 50px; height: 50px; transform: rotate(${truck.heading}deg); pointer-events: none;">
        <svg viewBox="0 0 100 100" style="width: 100%; height: 100%; filter: drop-shadow(0 0 6px ${color});">
          <path d="M50,50 L25,10 A35,35 0 0,1 75,10 Z" fill="${color}" opacity="0.25" />
        </svg>
      </div>

      <!-- Center Vehicle Pod -->
      <div style="width: 34px; height: 34px; border-radius: 50%; background: ${bgPod}; color: ${color}; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 16px ${glowColor}, inset 0 0 8px ${color}; border: 2px solid ${color}; transform: rotate(${truck.heading}deg); transition: transform 0.3s ease; z-index: 2;">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"><polygon points="3 11 22 2 13 21 11 13 3 11"/></svg>
      </div>

      <!-- Vehicle Plate Badge -->
      <div style="position: absolute; bottom: -6px; background: ${bgPod}; color: ${textPlate}; font-family: monospace; font-size: 8px; font-weight: 800; padding: 1px 5px; border-radius: 4px; white-space: nowrap; border: 1px solid ${color}; box-shadow: 0 2px 8px rgba(0,0,0,0.4); z-index: 3;">
        ${truck.plateNumber}
      </div>
    </div>
  `;

  return L.divIcon({
    html: svgIconHtml,
    className: '',
    iconSize: [46, 46],
    iconAnchor: [23, 23],
  });
}

export default function FleetLiveMap() {
  const navigate = useNavigate();
  const { fleet, isPlaying, speedMultiplier, togglePlay, changeSpeedMultiplier } = useSimulatedTelemetry(1);
  
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [mapThemeId, setMapThemeId] = useState<string>('voyager');

  const currentTheme = MAP_THEMES[mapThemeId] || MAP_THEMES.voyager;

  // Filter fleet based on user input
  const filteredFleet = fleet.filter((truck) => {
    const matchesSearch =
      truck.plateNumber.toLowerCase().includes(searchQuery.toLowerCase()) ||
      truck.driverName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      truck.refId.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesStatus =
      statusFilter === 'ALL' || truck.status.toUpperCase() === statusFilter.toUpperCase();

    return matchesSearch && matchesStatus;
  });

  return (
    <TooltipProvider>
      <Card className="border-black/[0.06] shadow-md rounded-[24px] bg-white overflow-hidden shrink-0">
        <CardHeader className="border-b border-black/[0.04] pb-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-[#FF5500] animate-ping" />
                <CardTitle className="text-base font-extrabold text-[#111] tracking-tight">Live Fleet Location Radar</CardTitle>
                <Badge variant="outline" className={`text-[10px] font-mono ${currentTheme.badgeColor}`}>
                  {currentTheme.name}
                </Badge>
              </div>
              <CardDescription className="text-xs text-[#6E6E80] mt-0.5">
                Real-time positioning across Saudi Arabia transport corridors
              </CardDescription>
            </div>

            {/* Controls & Toolbar */}
            <div className="flex flex-wrap items-center gap-2">
              
              {/* Map Theme Dropdown Selector */}
              <MapThemeSelector
                currentThemeId={mapThemeId}
                onThemeChange={(newTheme) => setMapThemeId(newTheme)}
              />

              {/* Search input */}
              <div className="relative">
                <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#6E6E80]" />
                <Input
                  type="text"
                  placeholder="Search truck, driver..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="h-8 pl-8 pr-3 text-xs w-36 sm:w-40 bg-[#F5F5F7] border-transparent focus-visible:bg-white focus-visible:ring-[#FF5500]"
                />
              </div>

              {/* Status Filter */}
              <Select value={statusFilter} onValueChange={(val) => setStatusFilter(val)}>
                <SelectTrigger className="h-8 text-xs w-36 bg-[#F5F5F7] border-transparent font-semibold">
                  <SelectValue placeholder="All Statuses" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ALL">All Statuses ({fleet.length})</SelectItem>
                  <SelectItem value="INTRANSIT">In Transit ({fleet.filter(f => f.status === 'InTransit').length})</SelectItem>
                  <SelectItem value="ATPICKUP">At Pickup ({fleet.filter(f => f.status === 'AtPickup').length})</SelectItem>
                  <SelectItem value="IDLE">Idle / Rest ({fleet.filter(f => f.status === 'Idle').length})</SelectItem>
                  <SelectItem value="COMPLETED">Completed ({fleet.filter(f => f.status === 'Completed').length})</SelectItem>
                </SelectContent>
              </Select>

              {/* Play/Pause Button */}
              <Tooltip>
                <TooltipTrigger>
                  <Button
                    size="sm"
                    variant={isPlaying ? "default" : "secondary"}
                    onClick={togglePlay}
                    className={`h-8 text-xs font-bold gap-1.5 ${
                      isPlaying ? 'bg-[#1C1C2E] hover:bg-black text-white' : 'bg-green-600 hover:bg-green-700 text-white'
                    }`}
                  >
                    {isPlaying ? <Pause size={12} /> : <Play size={12} />}
                    <span>{isPlaying ? 'Pause' : 'Play'}</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  <p className="text-xs">Toggle simulated GPS animation loop</p>
                </TooltipContent>
              </Tooltip>

              {/* Speed Multiplier Button */}
              <Tooltip>
                <TooltipTrigger>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => changeSpeedMultiplier(speedMultiplier === 1 ? 2 : speedMultiplier === 2 ? 5 : 1)}
                    className="h-8 text-xs font-bold gap-1 border-black/[0.08] hover:bg-[#F5F5F7]"
                  >
                    <FastForward size={12} className="text-[#FF5500]" />
                    <span>{speedMultiplier}x Speed</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  <p className="text-xs">Adjust simulation speed (1x, 2x, 5x)</p>
                </TooltipContent>
              </Tooltip>

            </div>
          </div>
        </CardHeader>

        <CardContent className="p-5 space-y-4">
          
          {/* View Mode Tabs (Radar Map | Fleet Matrix | Live Log Stream) */}
          <Tabs defaultValue="map" className="w-full">
            <div className="flex items-center justify-between mb-3">
              <TabsList className="bg-[#F5F5F7] p-1 rounded-xl">
                <TabsTrigger value="map" className="text-xs font-bold rounded-lg px-3 py-1 data-[state=active]:bg-white data-[state=active]:shadow-sm flex items-center gap-1.5">
                  <Map className="w-3.5 h-3.5 text-[#E8450F]" />
                  <span>Radar Map</span>
                </TabsTrigger>
                <TabsTrigger value="matrix" className="text-xs font-bold rounded-lg px-3 py-1 data-[state=active]:bg-white data-[state=active]:shadow-sm flex items-center gap-1.5">
                  <Table2 className="w-3.5 h-3.5 text-blue-600" />
                  <span>Fleet Matrix</span>
                </TabsTrigger>
                <TabsTrigger value="logs" className="text-xs font-bold rounded-lg px-3 py-1 data-[state=active]:bg-white data-[state=active]:shadow-sm flex items-center gap-1.5">
                  <Radio className="w-3.5 h-3.5 text-emerald-600 animate-pulse" />
                  <span>Telemetry Feed</span>
                </TabsTrigger>
              </TabsList>

              <div className="hidden md:flex items-center gap-3 text-xs font-bold text-[#6E6E80]">
                <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-black/[0.06] bg-[#FAFAFA]">
                  <span className="w-2 h-2 rounded-full bg-[#FF5500] animate-ping" />
                  {fleet.filter(f => f.status === 'InTransit').length} Active
                </span>
                <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-black/[0.06] bg-[#FAFAFA]">
                  <span className="w-2 h-2 rounded-full bg-[#0088FF]" />
                  {fleet.filter(f => f.status === 'AtPickup').length} At Pickup
                </span>
                <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-black/[0.06] bg-[#FAFAFA]">
                  <span className="w-2 h-2 rounded-full bg-[#64748B]" />
                  {fleet.filter(f => f.status === 'Idle').length} Standby
                </span>
              </div>
            </div>

            {/* TAB 1: RADAR MAP */}
            <TabsContent value="map" className="mt-0">
              <div className="h-[480px] rounded-[22px] overflow-hidden border border-black/[0.1] relative z-0 shadow-xl" style={{ background: currentTheme.previewColor }}>
                <MapContainer
                  center={[24.5000, 44.5000]}
                  zoom={6}
                  scrollWheelZoom={true}
                  style={{ height: '100%', width: '100%', zIndex: 0 }}
                >
                  <TileLayer
                    key={currentTheme.id}
                    attribution={currentTheme.attribution}
                    url={currentTheme.url}
                  />

                  {filteredFleet.map((truck) => (
                    <Marker
                      key={truck.tripId}
                      position={[truck.currentCoords.lat, truck.currentCoords.lng]}
                      icon={createNeonTruckDivIcon(truck, currentTheme.isDark)}
                    >
                      <Popup className={currentTheme.isDark ? "dark-map-popup" : ""} maxWidth={320}>
                        <div className="p-2 space-y-3 font-sans">
                          
                          <div className="flex items-center justify-between border-b border-gray-200 dark:border-white/10 pb-2">
                            <div>
                              <span className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">{truck.refId}</span>
                              <p className="text-base font-black leading-tight mt-0.5">{truck.plateNumber}</p>
                            </div>
                            <StatusBadge status={truck.status} />
                          </div>

                          <div className="grid grid-cols-2 gap-2 text-xs">
                            <div className="bg-gray-100 dark:bg-white/5 p-2 rounded-lg border border-black/[0.05] dark:border-white/5">
                              <p className="text-[9px] text-gray-400 font-bold uppercase">Driver</p>
                              <p className="font-bold truncate">{truck.driverName}</p>
                              <p className="text-[10px] text-gray-500">{truck.driverPhone}</p>
                            </div>
                            <div className="bg-gray-100 dark:bg-white/5 p-2 rounded-lg border border-black/[0.05] dark:border-white/5">
                              <p className="text-[9px] text-gray-400 font-bold uppercase">Speed & Progress</p>
                              <p className="font-bold text-[#FF5500] flex items-center gap-1">
                                <Gauge size={11} /> {truck.speedKmH} km/h
                              </p>
                              <p className="text-[10px] text-gray-500 font-medium">{truck.progressPercentage}% Completed</p>
                            </div>
                          </div>

                          <div className="text-xs bg-[#FF5500]/10 border border-[#FF5500]/20 p-2.5 rounded-lg">
                            <p className="text-[9px] text-[#FF5500] font-bold uppercase tracking-wider">Logistics Route</p>
                            <p className="font-semibold mt-0.5 truncate">{truck.originName}</p>
                            <p className="text-[10px] text-gray-400 font-bold my-0.5">↓ Destination</p>
                            <p className="font-semibold truncate">{truck.destinationName}</p>
                          </div>

                          <div className="pt-1 flex gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => navigate(`/trips/${truck.tripId}`)}
                              className="flex-1 h-8 text-xs font-bold gap-1"
                            >
                              <ExternalLink size={12} />
                              <span>Details</span>
                            </Button>
                            <Button
                              size="sm"
                              onClick={() => navigate(`/trips/${truck.tripId}/track`)}
                              className="flex-1 h-8 bg-[#FF5500] hover:bg-[#D94800] text-white text-xs font-bold gap-1 border-0"
                            >
                              <Navigation size={12} />
                              <span>Live Radar</span>
                            </Button>
                          </div>

                        </div>
                      </Popup>
                    </Marker>
                  ))}
                </MapContainer>

                {/* Floating Top Left HUD Info */}
                <div className={`absolute top-3 left-3 z-[400] px-3.5 py-2 rounded-xl shadow-lg border text-xs flex items-center gap-2 font-mono font-bold ${
                  currentTheme.isDark 
                    ? 'bg-[#090A0F]/85 backdrop-blur-xl border-white/10 text-white' 
                    : 'bg-white/90 backdrop-blur-xl border-black/[0.08] text-[#111]'
                }`}>
                  <span className="w-2.5 h-2.5 rounded-full bg-[#FF5500] animate-ping" />
                  <span>{filteredFleet.length} VEHICLES IN TELEMETRY RANGE</span>
                </div>

                {/* Floating Bottom HUD Bar */}
                <div className={`absolute bottom-3 left-3 right-3 sm:right-auto z-[400] px-4 py-2.5 rounded-xl shadow-xl border text-xs flex items-center gap-3 ${
                  currentTheme.isDark 
                    ? 'bg-[#090A0F]/90 backdrop-blur-xl border-white/10 text-white' 
                    : 'bg-white/95 backdrop-blur-xl border-black/[0.08] text-[#111]'
                }`}>
                  <ShieldCheck size={16} className="text-green-500 shrink-0" />
                  <div>
                    <p className="font-bold">Active Map Theme: {currentTheme.name}</p>
                    <p className="text-[10px] text-gray-400 font-mono">Simulated GPS Telemetry ({speedMultiplier}x Speed)</p>
                  </div>
                </div>
              </div>
            </TabsContent>

            {/* TAB 2: FLEET MATRIX TABLE */}
            <TabsContent value="matrix" className="mt-0">
              <div className="border border-black/[0.06] rounded-xl overflow-hidden min-h-[480px]">
                <Table>
                  <TableHeader className="bg-[#FAFAFA]">
                    <TableRow>
                      <TableHead className="text-[10px] uppercase font-bold text-[#9898A4]">Manifest ID</TableHead>
                      <TableHead className="text-[10px] uppercase font-bold text-[#9898A4]">Plate & Asset</TableHead>
                      <TableHead className="text-[10px] uppercase font-bold text-[#9898A4]">Driver Name</TableHead>
                      <TableHead className="text-[10px] uppercase font-bold text-[#9898A4]">Status</TableHead>
                      <TableHead className="text-[10px] uppercase font-bold text-[#9898A4]">Speed</TableHead>
                      <TableHead className="text-[10px] uppercase font-bold text-[#9898A4]">Progress</TableHead>
                      <TableHead className="text-[10px] uppercase font-bold text-[#9898A4] text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredFleet.map((truck) => (
                      <TableRow key={truck.tripId} className="hover:bg-[#FAFAFA]">
                        <TableCell className="font-mono text-xs font-bold text-[#FF5500]">{truck.refId}</TableCell>
                        <TableCell className="text-xs">
                          <p className="font-bold text-[#111]">{truck.plateNumber}</p>
                          <p className="text-[10px] text-gray-500">{truck.assetType}</p>
                        </TableCell>
                        <TableCell className="text-xs font-semibold text-[#111]">{truck.driverName}</TableCell>
                        <TableCell><StatusBadge status={truck.status} /></TableCell>
                        <TableCell className="text-xs font-bold text-[#111]">{truck.speedKmH} km/h</TableCell>
                        <TableCell className="w-36">
                          <div className="space-y-1">
                            <div className="flex justify-between text-[10px] font-bold text-gray-500">
                              <span>{truck.progressPercentage}%</span>
                              <span>{truck.distanceRemainingKm} km left</span>
                            </div>
                            <Progress value={truck.progressPercentage} className="h-1.5 bg-gray-100" />
                          </div>
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-1.5">
                            <Button size="sm" variant="ghost" className="h-7 text-xs font-bold" onClick={() => navigate(`/trips/${truck.tripId}`)}>
                              View
                            </Button>
                            <Button size="sm" className="h-7 text-xs font-bold bg-[#FF5500] hover:bg-[#D94800]" onClick={() => navigate(`/trips/${truck.tripId}/track`)}>
                              Track
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </TabsContent>

            {/* TAB 3: TELEMETRY LOGS */}
            <TabsContent value="logs" className="mt-0">
              <div className="bg-[#090A0F] text-white rounded-xl p-4 font-mono text-xs space-y-3 min-h-[480px] overflow-y-auto border border-white/10 shadow-2xl">
                <div className="flex items-center justify-between border-b border-white/10 pb-2">
                  <span className="text-[#FF5500] font-bold flex items-center gap-1.5">
                    <Activity size={14} className="animate-spin text-[#FF5500]" /> TELEMETRY STREAM FEED
                  </span>
                  <span className="text-[10px] text-gray-400">POLLING • {speedMultiplier * 1000}ms TICK</span>
                </div>
                {fleet.map((truck) => (
                  <div key={truck.tripId} className="bg-white/5 p-3 rounded-lg border border-white/5 flex flex-col sm:flex-row justify-between sm:items-center gap-2 hover:border-[#FF5500]/40 transition-colors">
                    <div>
                      <span className="text-[#FF5500] font-bold">[{truck.refId}]</span> <span className="text-white font-bold">{truck.plateNumber}</span> - {truck.driverName}
                      <p className="text-[11px] text-gray-400 mt-0.5">
                        Route: {truck.originName} ➔ {truck.destinationName}
                      </p>
                    </div>
                    <div className="text-right text-[11px]">
                      <p className="text-green-400 font-bold">GPS: {truck.currentCoords.lat.toFixed(5)}, {truck.currentCoords.lng.toFixed(5)}</p>
                      <p className="text-gray-400">Speed: {truck.speedKmH} km/h • Heading: {truck.heading}°</p>
                    </div>
                  </div>
                ))}
              </div>
            </TabsContent>

          </Tabs>

        </CardContent>
      </Card>
    </TooltipProvider>
  );
}
