import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** A calendar date as YYYY-MM-DD in the *viewer's* timezone.
 *
 * Never use `toISOString().split('T')[0]` for this. That is always UTC, so
 * for an India-based user (UTC+5:30) anything before 05:30 local reports
 * yesterday's date: opening the dashboard at 04:00 on the 28th made a
 * "Today" filter send date_from=27th and silently fold in a whole extra
 * day's attendance and cost. It breaks the other way too -- local midnight
 * on the 1st of the month converts to the last day of the *previous* month,
 * so a "This Month" filter started on 30 June.
 *
 * Attendance is stored as a site-local DATE (never a timestamp), so the
 * value compared against it has to be a local calendar date as well.
 * 'en-CA' is used purely because its short-date format is ISO-shaped.
 */
export function toLocalISODate(date: Date = new Date()): string {
  return date.toLocaleDateString('en-CA')
}

/** Compact relative time ("2h ago", "3d ago") for dense operational rows. */
export function timeAgo(dateString: string): string {
  const diffMs = Date.now() - new Date(dateString).getTime()
  const minutes = Math.round(diffMs / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.round(hours / 24)
  if (days < 30) return `${days}d ago`
  const months = Math.round(days / 30)
  return `${months}mo ago`
}
