import * as React from 'react'
import {
  CalendarDays,
  DollarSign,
  HardHat,
  Building,
  AlertCircle,
  UserCheck,
  UserPlus,
  ClipboardCheck,
} from 'lucide-react'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Badge } from '@/components/ui/badge'
import { fetchOneWorkerStatisticsApi, type WorkerStatistics } from '@/lib/api'

interface WorkerStatisticsSheetProps {
  workerId: string | null
  workerName?: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

/** Months to render in the calendar, ending on the worker's last recorded day.
 *  Bounded so a worker with three years of history does not render 36 grids. */
const CALENDAR_MONTHS = 3

/** Builds the month grids to display, anchored on the worker's own history
 *  rather than on today: someone who last worked in March should open on
 *  March, not on an empty current month. */
function buildMonths(dates: string[]): { label: string; year: number; month: number }[] {
  if (dates.length === 0) return []
  const last = new Date(`${dates[dates.length - 1]}T00:00:00`)
  const months: { label: string; year: number; month: number }[] = []
  for (let i = CALENDAR_MONTHS - 1; i >= 0; i--) {
    const d = new Date(last.getFullYear(), last.getMonth() - i, 1)
    months.push({
      label: d.toLocaleDateString('en-IN', { month: 'short', year: 'numeric' }),
      year: d.getFullYear(),
      month: d.getMonth(),
    })
  }
  return months
}

function MonthGrid({
  year,
  month,
  label,
  worked,
}: {
  year: number
  month: number
  label: string
  worked: Set<string>
}) {
  const first = new Date(year, month, 1)
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  // Monday-first, matching how a site week is read.
  const leading = (first.getDay() + 6) % 7

  const cells: (number | null)[] = [
    ...Array.from({ length: leading }, () => null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ]

  return (
    <div className="flex flex-col gap-1.5">
      <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">
        {label}
      </div>
      <div className="grid grid-cols-7 gap-1">
        {['M', 'T', 'W', 'T', 'F', 'S', 'S'].map((d, i) => (
          <div key={i} className="text-[9px] text-muted-foreground text-center font-medium">
            {d}
          </div>
        ))}
        {cells.map((day, i) => {
          if (day === null) return <div key={`pad-${i}`} />
          const iso = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
          const present = worked.has(iso)
          return (
            <div
              key={iso}
              title={present ? `Present on ${iso}` : iso}
              className={`aspect-square rounded-sm flex items-center justify-center text-[9px] font-mono ${
                present
                  ? 'bg-emerald-500/80 text-white font-bold'
                  : 'bg-muted/40 text-muted-foreground/50'
              }`}
            >
              {day}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function Stat({
  icon,
  label,
  value,
  hint,
}: {
  icon: React.ReactNode
  label: string
  value: React.ReactNode
  hint?: string
}) {
  return (
    <div className="border rounded-lg p-2.5 bg-card flex flex-col gap-1">
      <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
        {icon}
        {label}
      </div>
      <div className="text-base font-mono font-bold text-foreground tabular-nums">{value}</div>
      {hint && <div className="text-[10px] text-muted-foreground">{hint}</div>}
    </div>
  )
}

export function WorkerStatisticsSheet({
  workerId,
  workerName,
  open,
  onOpenChange,
}: WorkerStatisticsSheetProps) {
  const [stats, setStats] = React.useState<WorkerStatistics | null>(null)
  const [loading, setLoading] = React.useState(false)
  // "No history" and "the request failed" are different claims and must not
  // render as the same empty sheet.
  const [error, setError] = React.useState<string | null>(null)
  const [notFound, setNotFound] = React.useState(false)

  React.useEffect(() => {
    if (!open || !workerId) return
    let cancelled = false
    setLoading(true)
    setError(null)
    setNotFound(false)
    setStats(null)

    fetchOneWorkerStatisticsApi(workerId)
      .then((data) => {
        if (!cancelled) setStats(data)
      })
      .catch((err) => {
        if (cancelled) return
        // The endpoint 404s when a registered worker has never appeared in
        // attendance -- a real, ordinary state, not a failure.
        if (err?.response?.status === 404) setNotFound(true)
        else setError('Could not load this worker’s attendance history.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [open, workerId])

  const worked = React.useMemo(
    () => new Set(stats?.dates_worked ?? []),
    [stats]
  )
  const months = React.useMemo(() => buildMonths(stats?.dates_worked ?? []), [stats])

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <HardHat className="size-4 text-amber-500" />
            {stats?.name || workerName || 'Worker'}
          </SheetTitle>
          <SheetDescription>
            Attendance history, calculated from recorded attendance. Not editable.
          </SheetDescription>
        </SheetHeader>

        <div className="px-4 pb-6 flex flex-col gap-4">
          {loading && (
            <div className="py-12 text-center text-xs text-muted-foreground">
              Loading attendance history...
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-700 dark:text-rose-300">
              <AlertCircle className="size-3.5 shrink-0" />
              {error}
            </div>
          )}

          {notFound && (
            <div className="flex items-start gap-2 rounded-lg border border-border bg-muted/30 px-3 py-3 text-xs text-muted-foreground">
              <ClipboardCheck className="size-3.5 shrink-0 mt-0.5" />
              <span>
                This worker is on the register but has never appeared in an attendance
                report, so there is no history to show.
              </span>
            </div>
          )}

          {stats && (
            <>
              <div className="flex items-center gap-2 flex-wrap">
                {stats.is_registered ? (
                  <Badge variant="outline" className="text-[10px] border-emerald-500/30 text-emerald-600 dark:text-emerald-400">
                    <UserCheck className="size-3 mr-1" />
                    In register
                  </Badge>
                ) : (
                  <Badge variant="outline" className="text-[10px] border-amber-500/30 text-amber-600 dark:text-amber-400">
                    <UserPlus className="size-3 mr-1" />
                    Not yet in register
                  </Badge>
                )}
              </div>

              <div className="grid grid-cols-2 gap-2">
                <Stat
                  icon={<CalendarDays className="size-3" />}
                  label="Days worked"
                  value={stats.days_worked}
                  hint="Distinct days present"
                />
                <Stat
                  icon={<ClipboardCheck className="size-3" />}
                  label="Attendance records"
                  value={stats.attendance_count}
                  hint={
                    stats.attendance_count > stats.days_worked
                      ? 'More than days — recorded on multiple sites'
                      : 'Reports they appear in'
                  }
                />
                <Stat
                  icon={<DollarSign className="size-3" />}
                  label="Total earnings"
                  value={`₹${stats.total_earnings.toLocaleString('en-IN')}`}
                  hint={
                    stats.unpriced_man_days > 0
                      ? `Excludes ${stats.unpriced_man_days} day(s) with no wage recorded`
                      : 'From recorded wages'
                  }
                />
                <Stat
                  icon={<DollarSign className="size-3" />}
                  label="Average daily wage"
                  value={
                    stats.priced_man_days > 0
                      ? `₹${stats.avg_daily_wage.toLocaleString('en-IN')}`
                      : '—'
                  }
                  hint="Across days that had a wage"
                />
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="border rounded-lg p-2.5 bg-card">
                  <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground mb-1">
                    First seen
                  </div>
                  <div className="font-mono text-foreground">{stats.first_seen || '—'}</div>
                </div>
                <div className="border rounded-lg p-2.5 bg-card">
                  <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground mb-1">
                    Last seen
                  </div>
                  <div className="font-mono text-foreground">{stats.last_seen || '—'}</div>
                </div>
              </div>

              <div className="flex flex-col gap-2">
                <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground flex items-center gap-1.5">
                  <HardHat className="size-3" />
                  Trades worked
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {stats.trades.length === 0 ? (
                    <span className="text-xs text-muted-foreground">No trade recorded</span>
                  ) : (
                    stats.trades.map((t) => (
                      <Badge key={t} variant="outline" className="text-[10px]">
                        {t}
                      </Badge>
                    ))
                  )}
                </div>
              </div>

              <div className="flex flex-col gap-2">
                <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground flex items-center gap-1.5">
                  <Building className="size-3" />
                  Contractors worked under
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {stats.contractors.length === 0 ? (
                    <span className="text-xs text-muted-foreground">No contractor recorded</span>
                  ) : (
                    stats.contractors.map((c) => (
                      <Badge key={c} variant="outline" className="text-[10px]">
                        {c}
                      </Badge>
                    ))
                  )}
                </div>
              </div>

              {months.length > 0 && (
                <div className="flex flex-col gap-3 border-t pt-4">
                  <div className="flex items-center justify-between">
                    <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground flex items-center gap-1.5">
                      <CalendarDays className="size-3" />
                      Attendance calendar
                    </div>
                    <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
                      <span className="size-2.5 rounded-sm bg-emerald-500/80 inline-block" />
                      Present
                    </div>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    {months.map((m) => (
                      <MonthGrid
                        key={`${m.year}-${m.month}`}
                        year={m.year}
                        month={m.month}
                        label={m.label}
                        worked={worked}
                      />
                    ))}
                  </div>
                  <p className="text-[10px] text-muted-foreground">
                    Last {CALENDAR_MONTHS} months up to {stats.last_seen}. Earlier attendance is
                    counted in the totals above but not drawn here.
                  </p>
                </div>
              )}
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
