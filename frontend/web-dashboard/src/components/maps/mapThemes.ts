export interface MapTileTheme {
  id: string;
  name: string;
  category: 'Light' | 'Dark' | 'Satellite' | 'Terrain';
  url: string;
  attribution: string;
  badgeColor: string;
  isDark: boolean;
  previewColor: string;
}

export const MAP_THEMES: Record<string, MapTileTheme> = {
  voyager: {
    id: 'voyager',
    name: 'Voyager Light',
    category: 'Light',
    url: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>',
    badgeColor: 'border-blue-200 bg-blue-50 text-blue-700',
    isDark: false,
    previewColor: '#F4F5F7',
  },
  midnight: {
    id: 'midnight',
    name: 'Midnight Cyber',
    category: 'Dark',
    url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>',
    badgeColor: 'border-orange-900 bg-orange-950 text-orange-400',
    isDark: true,
    previewColor: '#0F1017',
  },
  positron: {
    id: 'positron',
    name: 'Positron Minimal',
    category: 'Light',
    url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>',
    badgeColor: 'border-slate-200 bg-slate-100 text-slate-700',
    isDark: false,
    previewColor: '#FAFAFA',
  },
  satellite: {
    id: 'satellite',
    name: 'Satellite Hybrid',
    category: 'Satellite',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping',
    badgeColor: 'border-emerald-800 bg-emerald-950 text-emerald-400',
    isDark: true,
    previewColor: '#0B1A12',
  },
  slate: {
    id: 'slate',
    name: 'Stadia Dark Slate',
    category: 'Dark',
    url: 'https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png',
    attribution: '&copy; <a href="https://stadiamaps.com/">Stadia Maps</a> &copy; <a href="https://openmaptiles.org/">OpenMapTiles</a>',
    badgeColor: 'border-purple-800 bg-purple-950 text-purple-300',
    isDark: true,
    previewColor: '#181825',
  },
  topo: {
    id: 'topo',
    name: 'Esri Topo Terrain',
    category: 'Terrain',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ, TomTom, Intermap',
    badgeColor: 'border-amber-200 bg-amber-50 text-amber-800',
    isDark: false,
    previewColor: '#F3EFE0',
  },
};
