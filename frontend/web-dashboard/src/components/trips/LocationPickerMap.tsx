import { useEffect, useRef, useState } from 'react';
import { MapContainer, TileLayer, Marker, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Search, MapPin } from 'lucide-react';

const pinIcon = L.divIcon({
  html: `<div style="background-color: #E8450F; color: white; padding: 5px; border-radius: 50% 50% 50% 0; transform: rotate(-45deg); box-shadow: 0 4px 6px rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center; width: 26px; height: 26px;"></div>`,
  className: '',
  iconSize: [26, 26],
  iconAnchor: [13, 26],
});

interface NominatimResult {
  display_name: string;
  lat: string;
  lon: string;
}

interface LocationPickerMapProps {
  label: string;
  lat: number | null;
  lng: number | null;
  onChange: (lat: number, lng: number) => void;
  /** Center the map here until a pin is placed. */
  defaultCenter?: [number, number];
  /** What this place is called, shown as the route label in delay reports. */
  name: string;
  onNameChange: (name: string) => void;
}

/**
 * Nominatim returns a full postal chain ("Khamis Mushait, Aseer Province,
 * 62454, Saudi Arabia"). A route label wants the place, not the address, so
 * take the leading segment — and the second as well when the first is just a
 * building or house number, which alone names nothing.
 */
function placeNameFrom(displayName: string): string {
  const parts = displayName.split(',').map((p) => p.trim()).filter(Boolean);
  if (parts.length === 0) return '';
  if (parts.length > 1 && /^\d+[A-Za-z]?$/.test(parts[0])) return `${parts[0]} ${parts[1]}`;
  return parts[0];
}

function ClickToPlacePin({ onPick }: { onPick: (lat: number, lng: number) => void }) {
  useMapEvents({
    click(e) {
      onPick(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

/** Recenters the map when a pin is set via address search (not on every render). */
function FlyToPin({ lat, lng }: { lat: number; lng: number }) {
  const map = useMap();
  useEffect(() => {
    map.flyTo([lat, lng], Math.max(map.getZoom(), 13), { animate: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lat, lng]);
  return null;
}

export default function LocationPickerMap({ label, lat, lng, onChange, name, onNameChange, defaultCenter = [24.7136, 46.6753] }: LocationPickerMapProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<NominatimResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const skipNextSearch = useRef(false);

  useEffect(() => {
    if (skipNextSearch.current) {
      skipNextSearch.current = false;
      return;
    }
    if (!query.trim()) {
      setResults([]);
      return;
    }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setSearching(true);
      try {
        const res = await fetch(
          `https://nominatim.openstreetmap.org/search?format=json&limit=5&q=${encodeURIComponent(query)}`
        );
        const data = await res.json();
        setResults(data);
        setShowResults(true);
      } catch {
        setResults([]);
      } finally {
        setSearching(false);
      }
    }, 400);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]);

  const pickResult = (r: NominatimResult) => {
    onChange(parseFloat(r.lat), parseFloat(r.lon));
    // Fill the name from the address that was just searched, so the common
    // path costs no extra typing. Overwrites deliberately: a new pin is a new
    // place, and carrying the old label over would silently mislabel it.
    onNameChange(placeNameFrom(r.display_name));
    skipNextSearch.current = true;
    setQuery(r.display_name);
    setShowResults(false);
  };

  const center: [number, number] = lat != null && lng != null ? [lat, lng] : defaultCenter;

  return (
    <div className="col-span-1 md:col-span-2 flex flex-col gap-1.5">
      <label className="text-xs font-bold text-[#111]">{label}</label>

      <div className="relative">
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#6E6E80]" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => results.length > 0 && setShowResults(true)}
            placeholder="Search an address…"
            className="w-full h-9 rounded-md bg-[#F5F5F7] border border-transparent focus:border-[#E8450F]/30 focus:bg-white pl-8 pr-3 text-sm outline-none transition-colors"
          />
        </div>
        {showResults && results.length > 0 && (
          <div className="absolute z-[500] mt-1 w-full bg-white rounded-md shadow-lg border border-black/[0.06] max-h-52 overflow-y-auto">
            {results.map((r, i) => (
              <button
                type="button"
                key={i}
                onClick={() => pickResult(r)}
                className="w-full text-left px-3 py-2 text-xs text-[#111] hover:bg-[#F5F5F7] border-b border-black/[0.04] last:border-b-0"
              >
                {r.display_name}
              </button>
            ))}
          </div>
        )}
      </div>

      <input
        type="text"
        value={name}
        onChange={(e) => onNameChange(e.target.value)}
        placeholder="Location name — e.g. Khamis Sorting Center"
        maxLength={120}
        className="w-full h-9 rounded-md bg-[#F5F5F7] border border-transparent focus:border-[#E8450F]/30 focus:bg-white px-3 text-sm outline-none transition-colors"
      />

      <div className="rounded-xl overflow-hidden border border-black/[0.06] h-[220px] relative z-0">
        <MapContainer center={center} zoom={lat != null ? 14 : 6} scrollWheelZoom style={{ height: '100%', width: '100%' }}>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <ClickToPlacePin onPick={onChange} />
          {lat != null && lng != null && (
            <>
              <FlyToPin lat={lat} lng={lng} />
              <Marker
                position={[lat, lng]}
                icon={pinIcon}
                draggable
                eventHandlers={{
                  dragend: (e) => {
                    const m = e.target as L.Marker;
                    const pos = m.getLatLng();
                    onChange(pos.lat, pos.lng);
                  },
                }}
              />
            </>
          )}
        </MapContainer>
      </div>

      <div className="flex items-center gap-1.5 text-[10px] text-[#6E6E80]">
        <MapPin size={11} />
        {lat != null && lng != null ? (
          <span>{lat.toFixed(6)}, {lng.toFixed(6)}</span>
        ) : (
          <span>Search an address or click the map to drop a pin</span>
        )}
      </div>
    </div>
  );
}
