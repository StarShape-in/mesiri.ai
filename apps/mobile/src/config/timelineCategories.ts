import { ArrowDownLeft, ArrowUpRight, LucideIcon } from 'lucide-react-native';
import { SemanticColors } from '../theme/tokens/semantic';

export type DotStyle = 'filled' | 'hollow';

export interface TimelineCategoryConfig {
  label: string;
  filterLabel: string;
  dotColorToken: keyof SemanticColors;
  dotStyle: DotStyle;
  Icon: LucideIcon;
}

// Keyed by the backend's `event_type` (mesiri.events.consumers.timeline_projector
// EVENT_SUMMARY_BUILDERS registry). Adding a new backend event type is one entry
// here — nothing else in the card renderer or filter row needs to change.
export const TIMELINE_CATEGORIES: Record<string, TimelineCategoryConfig> = {
  MaterialReceived: {
    label: 'Material received',
    filterLabel: 'Materials',
    dotColorToken: 'statusInfo',
    dotStyle: 'filled',
    Icon: ArrowDownLeft,
  },
  MaterialUsed: {
    label: 'Material used',
    filterLabel: 'Materials',
    dotColorToken: 'statusInfo',
    dotStyle: 'hollow',
    Icon: ArrowUpRight,
  },
};

export const DEFAULT_CATEGORY_CONFIG: TimelineCategoryConfig = {
  label: 'Activity',
  filterLabel: 'Other',
  dotColorToken: 'statusNeutral',
  dotStyle: 'filled',
  Icon: ArrowDownLeft,
};

export function getCategoryConfig(eventType: string): TimelineCategoryConfig {
  return TIMELINE_CATEGORIES[eventType] ?? DEFAULT_CATEGORY_CONFIG;
}

export interface FilterChipDef {
  key: string;
  label: string;
  eventTypes: string[] | null; // null = "All", no event_type filter applied
}

export const FILTER_CHIPS: FilterChipDef[] = [
  { key: 'all', label: 'All', eventTypes: null },
  { key: 'materials', label: 'Materials', eventTypes: ['MaterialReceived', 'MaterialUsed'] },
];
