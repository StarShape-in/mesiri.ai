import { PackagePlus, PackageMinus } from 'lucide-react'

// Shared across Portfolio/Project/Site Overview: today only two event types
// are ever projected into timeline_entries (see
// backend/src/mesiri/events/consumers/timeline_projector.py::AGGREGATE_TABLES).
// Add an entry here when a new Field Report domain starts writing to the
// timeline projection.
export const FIELD_ACTIVITY_META: Record<
  string,
  { label: string; slug: string; icon: typeof PackagePlus }
> = {
  MaterialReceived: { label: 'Material In', slug: 'material-in', icon: PackagePlus },
  MaterialUsed: { label: 'Material Out', slug: 'material-out', icon: PackageMinus },
}

export function describeEventType(eventType: string): string {
  return FIELD_ACTIVITY_META[eventType]?.label ?? eventType.replace(/([a-z])([A-Z])/g, '$1 $2')
}

export const STATUS_BADGES = {
  success: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20',
  warning: 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/20',
  critical: 'bg-rose-500/10 text-rose-700 dark:text-rose-400 border-rose-500/20',
  neutral: 'bg-muted text-muted-foreground border-border',
} as const

export function statusBadgeClass(status: string): string {
  return STATUS_BADGES[status as keyof typeof STATUS_BADGES] || STATUS_BADGES.neutral
}
