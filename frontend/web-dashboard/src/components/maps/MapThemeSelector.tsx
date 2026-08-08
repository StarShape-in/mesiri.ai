import { Sun, Moon, Globe, Layers, Compass, Palette } from 'lucide-react';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem, SelectGroup, SelectLabel } from '@/components/ui/select';
import { MAP_THEMES, MapTileTheme } from '@/components/maps/mapThemes';

interface MapThemeSelectorProps {
  currentThemeId: string;
  onThemeChange: (themeId: string) => void;
  className?: string;
}

export default function MapThemeSelector({ currentThemeId, onThemeChange, className }: MapThemeSelectorProps) {
  const currentTheme = MAP_THEMES[currentThemeId] || MAP_THEMES.voyager;

  return (
    <div className={`flex items-center gap-1.5 ${className || ''}`}>
      <Select value={currentThemeId} onValueChange={onThemeChange}>
        <SelectTrigger className="h-8 text-xs bg-[#F5F5F7] border border-black/[0.06] font-bold text-[#111] shadow-xs cursor-pointer focus:ring-[#FF5500]">
          <div className="flex items-center gap-1.5">
            <Palette size={13} className="text-[#FF5500]" />
            <span className="truncate">{currentTheme.name}</span>
          </div>
        </SelectTrigger>
        <SelectContent className="w-52">
          <SelectGroup>
            <SelectLabel className="text-[10px] uppercase font-bold text-[#9898A4]">Clean Light Themes</SelectLabel>
            <SelectItem value="voyager">
              <div className="flex items-center gap-2">
                <Sun size={12} className="text-amber-500" />
                <span>Voyager Light</span>
              </div>
            </SelectItem>
            <SelectItem value="positron">
              <div className="flex items-center gap-2">
                <Sun size={12} className="text-slate-400" />
                <span>Positron Minimal</span>
              </div>
            </SelectItem>
          </SelectGroup>

          <SelectGroup>
            <SelectLabel className="text-[10px] uppercase font-bold text-[#9898A4]">Dark Cyber Themes</SelectLabel>
            <SelectItem value="midnight">
              <div className="flex items-center gap-2">
                <Moon size={12} className="text-orange-400" />
                <span>Midnight Cyber</span>
              </div>
            </SelectItem>
            <SelectItem value="slate">
              <div className="flex items-center gap-2">
                <Moon size={12} className="text-purple-400" />
                <span>Stadia Dark Slate</span>
              </div>
            </SelectItem>
          </SelectGroup>

          <SelectGroup>
            <SelectLabel className="text-[10px] uppercase font-bold text-[#9898A4]">Satellite & Terrain</SelectLabel>
            <SelectItem value="satellite">
              <div className="flex items-center gap-2">
                <Globe size={12} className="text-emerald-500" />
                <span>Satellite Hybrid</span>
              </div>
            </SelectItem>
            <SelectItem value="topo">
              <div className="flex items-center gap-2">
                <Compass size={12} className="text-amber-700" />
                <span>Esri Topo Terrain</span>
              </div>
            </SelectItem>
          </SelectGroup>
        </SelectContent>
      </Select>
    </div>
  );
}
