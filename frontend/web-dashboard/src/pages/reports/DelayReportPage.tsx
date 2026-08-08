/**
 * Delay Report — the log, the on-time grid, and the analysis, behind one
 * filter bar.
 *
 * The three views deliberately share filter state rather than each owning its
 * own: choosing a company is meant to narrow all of them at once, so the
 * drill-down is "the same screens, filtered" instead of a separate screen per
 * question. Switching tabs keeps the scope you already set.
 *
 * **Colour is information here, not decoration.** Severity runs on one ramp
 * built from the app's own semantic tokens — success -> warning -> brand ->
 * danger — used identically for a delay badge, a grid cell and a KPI delta, so
 * "how bad" reads the same way everywhere. Structural chrome (which tab, which
 * rows) is ink; the period selector is brand, because it is the one control
 * that changes what every number on screen means.
 */

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, ArrowDownRight, ArrowUpRight, CalendarDays, ChevronDown, Download } from 'lucide-react';

import DashboardLayout from '@/components/layout/DashboardLayout';
import { Combobox } from '@/components/ui/combobox';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import {
  reportsService,
  type DelayDimension,
  type DelayGranularity,
  type DelayLogRow,
} from '@/services/reportsService';
import { customerService } from '@/services/customerService';
import { DELAY_REASON_LABELS, type DelayReason } from '@/services/tripService';
import { downloadCSV } from '@/utils/exportUtils';

type Tab = 'log' | 'grid' | 'analysis';

/** Stands in for "no company filter" — cmdk cannot carry an empty item value. */
const ALL_COMPANIES = '__all__';

/**
 * How far back to look, and how finely to slice it — two separate things.
 *
 * Bucketing a year *by year* collapses the grid to a single column and hides
 * the trend that made looking at a year worthwhile. So each range carries the
 * bucket that keeps a readable number of columns and matches how the client's
 * own sheet is laid out: a year read monthly, a quarter weekly, shorter
 * ranges daily.
 */
const PERIODS: { id: string; label: string; days: number; bucket: DelayGranularity }[] = [
  { id: 'today', label: 'Today', days: 1, bucket: 'day' },
  { id: 'week', label: 'Week', days: 7, bucket: 'day' },
  { id: 'month', label: 'Month', days: 30, bucket: 'day' },
  { id: 'quarter', label: 'Quarter', days: 90, bucket: 'week' },
  { id: 'year', label: 'Year', days: 365, bucket: 'month' },
];

/**
 * A custom range has no preset bucket, so pick one by span using the same
 * reasoning as the presets above: enough columns to show a trend, few enough
 * to read. The thresholds match where the presets themselves switch over.
 */
function bucketForSpan(days: number): DelayGranularity {
  return days > 120 ? 'month' : days > 45 ? 'week' : 'day';
}

const DIMENSIONS: { id: DelayDimension; label: string }[] = [
  { id: 'route', label: 'Route' },
  { id: 'driver', label: 'Driver' },
  { id: 'customer', label: 'Company' },
  { id: 'vehicle', label: 'Truck' },
];

function isoDaysAgo(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

const isoToday = () => new Date().toISOString().slice(0, 10);

/**
 * "8 Jul – 7 Aug 2026", with years on both ends when the range crosses one.
 *
 * Always spells the month, because this exists to be unambiguous: a date input
 * renders in the browser's locale, where 08-07-2026 is 8 July in most of the
 * world and 7 August in the US. "8 Jul" cannot be read two ways.
 */
function fmtRange(startIso: string, endIso: string): string {
  const [start, end] = [new Date(startIso), new Date(endIso)];
  const sameYear = start.getFullYear() === end.getFullYear();
  const opts: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short' };
  const fmt = (d: Date, withYear: boolean) =>
    d.toLocaleDateString(undefined, withYear ? { ...opts, year: 'numeric' } : opts);
  if (startIso === endIso) return fmt(start, true);
  return `${fmt(start, !sameYear)} – ${fmt(end, true)}`;
}

/**
 * "6 Aug 2026" — the page's only date format.
 *
 * `toLocaleDateString()` with no options yields 8/6/2026 or 06/08/2026
 * depending on the reader, and Chrome takes a date input's format from the OS
 * region while taking this one from the JS locale, so the two could disagree
 * *on the same screen*. Spelling the month removes the question.
 */
const fmtDate = (iso: string | Date) =>
  new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });

/** Same, with the clock time — for the CSV, where the hour matters. */
const fmtDateTime = (iso: string | Date) =>
  `${fmtDate(iso)}, ${new Date(iso).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}`;

const daysBetween = (startIso: string, endIso: string) =>
  Math.max(1, Math.round((Date.parse(endIso) - Date.parse(startIso)) / 86_400_000));

function reasonLabel(reason: string | null): string {
  if (!reason || reason === 'Unrecorded') return 'Not recorded';
  return DELAY_REASON_LABELS[reason as DelayReason] ?? reason;
}

/** One severity ramp, used for every "how bad is this" signal on the page. */
const TONE = {
  good: 'bg-success-bg text-success',
  minor: 'bg-warning-bg text-warning',
  major: 'bg-brand-light text-brand',
  bad: 'bg-danger-bg text-danger',
  none: 'text-faint',
} as const;

const delayTone = (hours: number) => (hours >= 4 ? TONE.bad : hours >= 2 ? TONE.major : TONE.minor);
const pctTone = (pct: number | null) =>
  pct === null ? TONE.none : pct >= 95 ? TONE.good : pct >= 85 ? TONE.minor : pct >= 60 ? TONE.major : TONE.bad;

function fmtDelay(hours: number) {
  const h = Math.floor(hours);
  const m = Math.round((hours - h) * 60);
  return h === 0 ? `${m}m` : m === 0 ? `${h}h` : `${h}h ${m}m`;
}

/** More delay is worse, so a rise is danger — the opposite of a revenue chart. */
function Delta({ value, suffix = '%' }: { value: number | null; suffix?: string }) {
  if (value === null || value === 0) return <span className="text-[11px] text-faint">—</span>;
  const worse = value > 0;
  const Icon = worse ? ArrowUpRight : ArrowDownRight;
  return (
    <span className={`text-[11px] font-semibold inline-flex items-center gap-0.5 tabular-nums ${worse ? 'text-danger' : 'text-success'}`}>
      <Icon size={12} strokeWidth={2.5} />{Math.abs(value)}{suffix}
    </span>
  );
}

function SegBtn({ active, onClick, children, tone = 'ink' }: {
  active: boolean; onClick: () => void; children: React.ReactNode; tone?: 'ink' | 'brand';
}) {
  const on = tone === 'brand' ? 'bg-brand text-white' : 'bg-ink text-white';
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-3 h-8 text-xs font-semibold whitespace-nowrap transition-colors ${
        active ? on : 'bg-white text-subtle hover:bg-black/[0.03]'
      }`}
    >
      {children}
    </button>
  );
}

/**
 * Which view you are looking at is navigation, not a filter — so it reads as
 * tabs above the bar rather than as another segmented control inside it.
 * Previously both were the same `Seg` component differing only in colour,
 * which made ten buttons in a row look like one undifferentiated strip.
 */
function TabLink({ active, onClick, children }: {
  active: boolean; onClick: () => void; children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={active ? 'page' : undefined}
      className={`relative pb-2.5 text-sm font-semibold whitespace-nowrap transition-colors ${
        active
          ? 'text-ink after:absolute after:inset-x-0 after:-bottom-px after:h-0.5 after:bg-brand after:rounded-full'
          : 'text-subtle hover:text-ink'
      }`}
    >
      {children}
    </button>
  );
}

const Seg = ({ children }: { children: React.ReactNode }) => (
  <div className="flex rounded-lg overflow-hidden border border-black/[0.08] divide-x divide-black/[0.06]">{children}</div>
);

const Card = ({ children, className = '' }: { children: React.ReactNode; className?: string }) => (
  <div className={`bg-white rounded-lg border border-black/[0.06] shadow-sm ${className}`}>{children}</div>
);

const Micro = ({ children }: { children: React.ReactNode }) => (
  <p className="text-[10px] uppercase tracking-[0.08em] text-faint font-bold">{children}</p>
);

/**
 * The period control, as one pill that states the range it resolved to.
 *
 * Five buttons reading Today/Week/Month/Quarter/Year never said *which* days
 * they meant — "Month" is only 30 days back if you already know that. Showing
 * the resolved dates costs a click to change and buys somewhere to put a
 * custom range, which the report had no way to express at all.
 */
function PeriodPicker({ periodId, startDate, endDate, onPreset, onCustom }: {
  periodId: string;
  startDate: string;
  endDate: string;
  onPreset: (id: string) => void;
  onCustom: (start: string, end: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [draftStart, setDraftStart] = useState(startDate);
  const [draftEnd, setDraftEnd] = useState(endDate);

  const isCustom = periodId === 'custom';
  const label = isCustom ? 'Custom range' : PERIODS.find((p) => p.id === periodId)?.label ?? 'Month';
  const invalid = !draftStart || !draftEnd || draftStart > draftEnd;

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        // Re-seed the draft from the applied range each time it opens, so a
        // half-typed range that was never applied does not linger.
        if (next) { setDraftStart(startDate); setDraftEnd(endDate); }
        setOpen(next);
      }}
    >
      <PopoverTrigger asChild>
        <button
          type="button"
          className="h-8 inline-flex items-center gap-2 rounded-lg border border-black/[0.08] bg-white px-2.5 text-xs transition-colors hover:bg-black/[0.02] focus:outline-none focus:border-brand"
        >
          <CalendarDays size={14} className="text-subtle shrink-0" />
          <span className="font-semibold text-ink whitespace-nowrap">{label}</span>
          <span className="text-subtle tabular-nums whitespace-nowrap">{fmtRange(startDate, endDate)}</span>
          <ChevronDown size={13} className="text-faint shrink-0" />
        </button>
      </PopoverTrigger>

      <PopoverContent align="start" className="w-64 p-1.5">
        {PERIODS.map((p) => (
          <button
            key={p.id}
            type="button"
            onClick={() => { onPreset(p.id); setOpen(false); }}
            className={`w-full flex items-center justify-between rounded-md px-2.5 py-1.5 text-xs transition-colors ${
              periodId === p.id ? 'bg-brand-light text-brand font-semibold' : 'text-ink hover:bg-black/[0.03]'
            }`}
          >
            <span>{p.label}</span>
            <span className="text-[11px] text-faint tabular-nums">
              {p.days === 1 ? 'today' : `${p.days} days`}
            </span>
          </button>
        ))}

        <div className="mt-1.5 border-t border-black/[0.06] pt-2 px-1">
          <Micro>Custom range</Micro>
          <div className="mt-1.5 flex items-center gap-1.5">
            <label className="flex-1 min-w-0">
              <span className="block text-[10px] text-faint font-semibold mb-0.5">From</span>
              <input
                type="date"
                value={draftStart}
                max={draftEnd || undefined}
                onChange={(e) => setDraftStart(e.target.value)}
                className="h-7 w-full min-w-0 rounded-md border border-black/[0.08] px-1.5 text-[11px] text-ink outline-none focus:border-brand"
              />
            </label>
            <label className="flex-1 min-w-0">
              <span className="block text-[10px] text-faint font-semibold mb-0.5">To</span>
              <input
                type="date"
                value={draftEnd}
                min={draftStart || undefined}
                max={isoToday()}
                onChange={(e) => setDraftEnd(e.target.value)}
                className="h-7 w-full min-w-0 rounded-md border border-black/[0.08] px-1.5 text-[11px] text-ink outline-none focus:border-brand"
              />
            </label>
          </div>

          {/*
            Date inputs render in the browser's locale, so "08-07-2026" is
            8 July to one reader and 7 August to another. Echoing the draft
            back with the month spelled out is the only way the picker can
            state which one it actually took.
          */}
          <p className="mt-1.5 text-[10px] text-subtle tabular-nums">
            {invalid
              ? draftStart && draftEnd
                ? 'The end date is before the start date.'
                : 'Pick both dates.'
              : fmtRange(draftStart, draftEnd)}
          </p>

          <button
            type="button"
            disabled={invalid}
            onClick={() => { onCustom(draftStart, draftEnd); setOpen(false); }}
            className="mt-1.5 w-full h-7 rounded-md bg-ink text-white text-[11px] font-semibold transition-opacity disabled:opacity-35 disabled:cursor-not-allowed"
          >
            Apply
          </button>
        </div>
      </PopoverContent>
    </Popover>
  );
}

export default function DelayReportPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>('log');
  const [periodId, setPeriodId] = useState('month');
  const [custom, setCustom] = useState<{ start: string; end: string } | null>(null);
  const [customerId, setCustomerId] = useState('');
  const [dimension, setDimension] = useState<DelayDimension>('route');
  const [needsReasonOnly, setNeedsReasonOnly] = useState(false);
  const [page, setPage] = useState(1);

  // A preset resolves to a range; a custom range is already one. Both end up as
  // the same {startDate, endDate, granularity}, so nothing downstream has to
  // know which of the two the user picked.
  const { startDate, endDate, granularity } = useMemo(() => {
    if (periodId === 'custom' && custom) {
      return {
        startDate: custom.start,
        endDate: custom.end,
        granularity: bucketForSpan(daysBetween(custom.start, custom.end)),
      };
    }
    const p = PERIODS.find((x) => x.id === periodId) ?? PERIODS[2];
    return { startDate: isoDaysAgo(p.days), endDate: isoToday(), granularity: p.bucket };
  }, [periodId, custom]);

  const filters = useMemo(
    () => ({
      startDate,
      endDate,
      ...(customerId ? { customer_id: customerId } : {}),
      ...(needsReasonOnly ? { needs_reason: 'true' as const } : {}),
    }),
    [startDate, endDate, customerId, needsReasonOnly],
  );

  const { data: customers } = useQuery({
    queryKey: ['customers-select'],
    queryFn: () => customerService.getAll({ per_page: 200 }),
  });

  const log = useQuery({
    queryKey: ['delay-log', filters, page],
    queryFn: () => reportsService.getDelayLog({ ...filters, page, per_page: 25 }),
    enabled: tab === 'log',
  });
  const grid = useQuery({
    queryKey: ['delay-grid', filters, dimension, granularity],
    queryFn: () => reportsService.getDelayGrid({ ...filters, dimension, granularity }),
    enabled: tab === 'grid',
  });
  const analysis = useQuery({
    queryKey: ['delay-analysis', filters, granularity],
    queryFn: () => reportsService.getDelayAnalysis({ ...filters, granularity }),
    enabled: tab === 'analysis',
  });

  const handleExport = () => {
    const rows = log.data?.data ?? [];
    if (!rows.length) return;
    downloadCSV(
      rows.map((r: DelayLogRow) => ({
        Date: fmtDateTime(r.date),
        Trip: r.trip_ref ?? '',
        Route: r.route,
        Company: r.customer,
        Driver: r.driver,
        Truck: r.vehicle,
        'Planned arrival': fmtDateTime(r.planned_arrival),
        'Actual arrival': fmtDateTime(r.actual_arrival),
        'Delay (h)': r.delay_hours,
        'Waiting (h)': r.dwell_hours ?? '',
        Reason: reasonLabel(r.delay_reason),
        Note: r.delay_note ?? '',
      })),
      `mercon_delays_${startDate}_to_${endDate}.csv`,
    );
  };

  const busy = log.isLoading || grid.isLoading || analysis.isLoading;

  // "All companies" needs a value cmdk can carry; an empty string is not one,
  // so it travels as a sentinel and is mapped back to "" (meaning unfiltered)
  // at the boundary rather than leaking into the query.
  const companyOptions = useMemo(
    () => [
      { value: ALL_COMPANIES, label: 'All companies' },
      ...(customers?.data ?? []).map((c: any) => ({ value: c.id as string, label: c.name as string })),
    ],
    [customers],
  );

  return (
    <DashboardLayout active="Reports" title="Delay Report" pageTitle="Delay Report">
      <div className="px-6 pb-10 space-y-4">

        {/* ── Which view: navigation, so it sits above the filters ──────── */}
        <div className="flex items-center gap-5 border-b border-black/[0.08]">
          <TabLink active={tab === 'log'} onClick={() => setTab('log')}>Log</TabLink>
          <TabLink active={tab === 'grid'} onClick={() => setTab('grid')}>On-time grid</TabLink>
          <TabLink active={tab === 'analysis'} onClick={() => setTab('analysis')}>Analysis</TabLink>
        </div>

        {/* ── Filter bar: scope, shared by all three views ──────────────── */}
        <Card className="p-3 flex flex-wrap items-center gap-2">
          <PeriodPicker
            periodId={periodId}
            startDate={startDate}
            endDate={endDate}
            onPreset={(id) => { setPeriodId(id); setCustom(null); setPage(1); }}
            onCustom={(start, end) => { setCustom({ start, end }); setPeriodId('custom'); setPage(1); }}
          />

          <Combobox
            options={companyOptions}
            value={customerId || ALL_COMPANIES}
            onChange={(v) => { setCustomerId(v === ALL_COMPANIES ? '' : v); setPage(1); }}
            placeholder="All companies"
            searchPlaceholder="Search companies…"
            emptyText="No company matches."
            triggerClassName="h-8 w-[190px] text-xs font-semibold text-ink border-black/[0.08] rounded-lg px-2.5"
          />

          {tab === 'log' && (
            <label className="flex items-center gap-1.5 text-xs font-medium text-subtle cursor-pointer select-none">
              <input
                type="checkbox"
                checked={needsReasonOnly}
                onChange={(e) => { setNeedsReasonOnly(e.target.checked); setPage(1); }}
                className="accent-[#E8450F]"
              />
              Needs a reason
            </label>
          )}

          {tab === 'grid' && (
            <div className="flex items-center gap-1.5">
              <span className="text-[11px] text-faint font-semibold uppercase tracking-wide">Rows</span>
              <Seg>
                {DIMENSIONS.map((d) => (
                  <SegBtn key={d.id} active={dimension === d.id} onClick={() => setDimension(d.id)}>{d.label}</SegBtn>
                ))}
              </Seg>
            </div>
          )}

          <div className="ml-auto flex items-center gap-2">
            {busy && <span className="text-[11px] text-faint">Loading…</span>}
            {tab === 'log' && (
              <button
                type="button"
                onClick={handleExport}
                disabled={!log.data?.data?.length}
                className="h-8 px-3 rounded-lg border border-black/[0.08] text-xs font-semibold text-ink hover:bg-black/[0.03] inline-flex items-center gap-1.5 disabled:opacity-40"
              >
                <Download size={13} /> Export CSV
              </button>
            )}
          </div>
        </Card>

        {/*
          The applied range, spelled out, immediately above the results it
          produced. A locale-formatted pill can be misread (08-07 is two
          different days depending on where you are); "8 Jul 2026" cannot.
        */}
        <p className="text-xs text-subtle">
          Arrivals between <span className="font-semibold text-ink">{fmtRange(startDate, endDate)}</span>
          {tab === 'log' && log.data?.meta && (
            <> · <span className="font-semibold text-ink tabular-nums">{log.data.meta.total}</span> late</>
          )}
        </p>

        {/* ── Log ───────────────────────────────────────────────────────── */}
        {tab === 'log' && (
          <Card className="overflow-hidden">
            {log.isError && <p className="p-6 text-sm text-danger">Could not load the delay log. Try again.</p>}
            {log.data && log.data.data.length === 0 && (
              // "Nothing to explain" alone reads as good news, and looks
              // identical whether the fleet ran perfectly or nobody entered a
              // planned arrival time. Say which.
              <div className="p-6 space-y-1.5">
                <p className="text-sm font-semibold text-ink">
                  No delays over {log.data.meta.threshold_minutes} minutes in this period.
                </p>
                <p className="text-xs text-subtle max-w-xl leading-relaxed">
                  A trip only appears here once it has both a planned arrival time and a recorded actual
                  arrival. Trips created without a planned time can never be measured, so an empty report
                  can mean the schedule was missing rather than that everything ran on time.
                </p>
              </div>
            )}
            {log.data && log.data.data.length > 0 && (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="bg-black/[0.02] border-b border-black/[0.06]">
                        {['Date', 'Route', 'Trip', 'Company', 'Driver', 'Truck'].map((h) => (
                          <th key={h} className="text-left font-bold text-faint uppercase tracking-wide text-[10px] px-3 py-2.5">{h}</th>
                        ))}
                        <th className="text-right font-bold text-faint uppercase tracking-wide text-[10px] px-3 py-2.5">Delay</th>
                        <th className="text-right font-bold text-faint uppercase tracking-wide text-[10px] px-3 py-2.5">Waiting</th>
                        <th className="text-left font-bold text-faint uppercase tracking-wide text-[10px] px-3 py-2.5">Reason</th>
                      </tr>
                    </thead>
                    <tbody>
                      {log.data.data.map((r) => (
                        <tr
                          key={r.stop_id}
                          onClick={() => navigate(`/trips/${r.trip_id}`)}
                          className="border-b border-black/[0.04] last:border-0 hover:bg-brand-light/60 cursor-pointer transition-colors"
                        >
                          <td className="px-3 py-2.5 text-subtle tabular-nums whitespace-nowrap">
                            {fmtDate(r.date)}
                          </td>
                          <td className="px-3 py-2.5 font-medium text-ink whitespace-nowrap">{r.route}</td>
                          <td className="px-3 py-2.5 text-faint tabular-nums whitespace-nowrap">{r.trip_ref ?? '—'}</td>
                          <td className="px-3 py-2.5 text-ink-soft whitespace-nowrap">{r.customer}</td>
                          <td className="px-3 py-2.5 text-ink-soft whitespace-nowrap">{r.driver}</td>
                          <td className="px-3 py-2.5 text-ink-soft tabular-nums whitespace-nowrap">{r.vehicle}</td>
                          <td className="px-3 py-2.5 text-right whitespace-nowrap">
                            <span className={`inline-block px-2 py-0.5 rounded-full text-[11px] font-bold tabular-nums ${delayTone(r.delay_hours)}`}>
                              +{fmtDelay(r.delay_hours)}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-right text-faint tabular-nums whitespace-nowrap">
                            {r.dwell_hours === null ? '—' : fmtDelay(r.dwell_hours)}
                          </td>
                          <td className="px-3 py-2.5 whitespace-nowrap">
                            {r.needs_reason ? (
                              <span className="inline-flex items-center gap-1 text-brand font-bold">
                                <AlertTriangle size={11} /> Add reason
                              </span>
                            ) : (
                              <span className="text-ink-soft">
                                {reasonLabel(r.delay_reason)}
                                {r.delay_note && <span className="text-faint"> · {r.delay_note}</span>}
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="flex items-center justify-between px-3 py-2.5 border-t border-black/[0.06] text-xs text-subtle">
                  <span>
                    <strong className="text-ink tabular-nums">{log.data.meta.total}</strong> delayed arrival{log.data.meta.total === 1 ? '' : 's'}
                    {log.data.meta.truncated && ' · showing the most recent, narrow the range for a full count'}
                  </span>
                  <span className="flex items-center gap-2">
                    <button type="button" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}
                      className="h-7 px-2.5 rounded-md border border-black/[0.08] font-semibold disabled:opacity-40 hover:bg-black/[0.03]">Prev</button>
                    <span className="tabular-nums">Page {log.data.meta.page} of {Math.max(log.data.meta.total_pages, 1)}</span>
                    <button type="button" disabled={page >= log.data.meta.total_pages} onClick={() => setPage((p) => p + 1)}
                      className="h-7 px-2.5 rounded-md border border-black/[0.08] font-semibold disabled:opacity-40 hover:bg-black/[0.03]">Next</button>
                  </span>
                </div>
              </>
            )}
          </Card>
        )}

        {/* ── On-time grid ──────────────────────────────────────────────── */}
        {tab === 'grid' && (
          <Card className="overflow-hidden">
            {grid.isError && <p className="p-6 text-sm text-danger">Could not load the grid. Try again.</p>}
            {grid.data && grid.data.rows.length === 0 && (
              <p className="p-6 text-sm text-subtle">No arrivals with a planned time in this period.</p>
            )}
            {grid.data && grid.data.rows.length > 0 && (
              <>
                <div className="flex items-center gap-3 px-3 py-2 border-b border-black/[0.06] text-[10px] text-faint">
                  <span className="uppercase tracking-wide font-bold">On-time %</span>
                  {[['≥95', TONE.good], ['85–94', TONE.minor], ['60–84', TONE.major], ['&lt;60', TONE.bad]].map(([l, t]) => (
                    <span key={l as string} className={`px-1.5 py-0.5 rounded font-bold ${t}`} dangerouslySetInnerHTML={{ __html: l as string }} />
                  ))}
                  <span className="ml-auto">– = nothing ran</span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="bg-black/[0.02] border-b border-black/[0.06]">
                        <th className="text-left font-bold text-faint uppercase tracking-wide text-[10px] px-3 py-2.5 sticky left-0 bg-[#FAFAFA]">
                          {DIMENSIONS.find((d) => d.id === grid.data!.dimension)?.label}
                        </th>
                        <th className="text-right font-bold text-faint uppercase tracking-wide text-[10px] px-3 py-2.5">Overall</th>
                        {grid.data.periods.map((p) => (
                          <th key={p.key} className="text-right font-bold text-faint uppercase tracking-wide text-[10px] px-3 py-2.5 whitespace-nowrap">{p.label}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      <tr className="border-b-2 border-black/[0.08] bg-black/[0.015]">
                        <td className="px-3 py-2.5 font-bold text-ink sticky left-0 bg-[#FAFAFA]">All</td>
                        <td className="px-3 py-2.5" />
                        {grid.data.all_rows.cells.map((c) => (
                          <td key={c.period} className={`px-3 py-2.5 text-right font-semibold tabular-nums ${pctTone(c.pct)}`}>
                            {c.pct === null ? '–' : `${c.pct}%`}
                          </td>
                        ))}
                      </tr>
                      {grid.data.rows.map((row) => (
                        <tr key={row.key} className="border-b border-black/[0.04] last:border-0">
                          <td className="px-3 py-2.5 font-medium text-ink whitespace-nowrap sticky left-0 bg-white">{row.label}</td>
                          <td className={`px-3 py-2.5 text-right font-bold tabular-nums ${pctTone(row.overall_pct)}`}>
                            {row.overall_pct === null ? '–' : `${row.overall_pct}%`}
                          </td>
                          {row.cells.map((c) => (
                            <td key={c.period} className={`px-3 py-2.5 text-right tabular-nums ${pctTone(c.pct)}`}>
                              {c.pct === null ? '–' : `${c.pct}%`}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </Card>
        )}

        {/* ── Analysis ──────────────────────────────────────────────────── */}
        {tab === 'analysis' && (
          <div className="space-y-4">
            {analysis.isError && <p className="p-6 text-sm text-danger">Could not load the analysis. Try again.</p>}
            {analysis.data && (
              <>
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                  <Kpi label="Hours lost" value={`${analysis.data.totals.hours_lost}h`} delta={analysis.data.change.hours_lost_pct} />
                  <Kpi label="Delayed arrivals" value={analysis.data.totals.delayed} raw={analysis.data.change.delayed_count} />
                  <Kpi label="On-time" value={analysis.data.totals.on_time_pct === null ? '—' : `${analysis.data.totals.on_time_pct}%`}
                    tone={pctTone(analysis.data.totals.on_time_pct)} />
                  <Kpi label="Unexplained" value={analysis.data.totals.unexplained}
                    hint={analysis.data.totals.unexplained > 0 ? 'nobody logged a reason' : 'all accounted for'} />
                </div>

                {analysis.data.trend.length > 0 && (
                  <Card className="p-4">
                    <Micro>Hours lost over time</Micro>
                    <div className="flex items-end gap-1.5 h-32 mt-3">
                      {(() => {
                        const max = Math.max(...analysis.data!.trend.map((t) => t.hours_lost), 1);
                        return analysis.data!.trend.map((t) => (
                          // h-full matters: the bar's height is a percentage,
                          // which resolves to zero unless this column has a
                          // definite height to resolve against.
                          <div key={t.period} className="flex-1 h-full flex flex-col justify-end items-center gap-1 min-w-0 group">
                            <span className="text-[9px] tabular-nums text-faint group-hover:text-brand transition-colors">{t.hours_lost}</span>
                            <div
                              className="w-full bg-brand/85 group-hover:bg-brand rounded-t-sm transition-colors"
                              style={{ height: `${Math.max((t.hours_lost / max) * 100, 2)}%` }}
                              title={`${t.label}: ${t.hours_lost}h`}
                            />
                            <span className="text-[9px] text-faint truncate w-full text-center">{t.label}</span>
                          </div>
                        ));
                      })()}
                    </div>
                  </Card>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <Board title="Worst routes — hours lost"
                    rows={analysis.data.routes.map((r) => ({
                      label: r.label, value: `${r.hours_lost}h`, weight: r.hours_lost,
                      delta: <Delta value={r.change_pct} />,
                    }))} />
                  <Board title="Drivers — late / total arrivals"
                    rows={analysis.data.drivers.map((d) => ({
                      label: d.label, value: `${d.late} / ${d.total}`, weight: d.late,
                      delta: <Delta value={d.change === 0 ? null : d.change} suffix="" />,
                    }))} />
                  <Board title="Reasons — share of delays"
                    rows={analysis.data.reasons.map((r) => ({
                      label: reasonLabel(r.reason), value: `${r.share_pct}%`, weight: r.share_pct,
                      delta: <Delta value={r.change_pt === 0 ? null : r.change_pt} suffix="pt" />,
                    }))} />
                  <Board title="Trucks — breakdowns & repair spend"
                    empty="No breakdown-related delays in this period."
                    rows={analysis.data.vehicles.map((v) => ({
                      label: v.label, value: `${v.breakdowns} · SAR ${v.maintenance_cost.toLocaleString()}`,
                      weight: v.breakdowns, delta: <Delta value={v.change === 0 ? null : v.change} suffix="" />,
                    }))} />
                </div>

                <p className="text-[11px] text-faint">
                  Change is against {fmtDate(analysis.data.previous_range.start)} – {fmtDate(analysis.data.previous_range.end)}
                </p>
              </>
            )}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

function Kpi({ label, value, delta, raw, tone, hint }: {
  label: string; value: React.ReactNode; delta?: number | null; raw?: number; tone?: string; hint?: string;
}) {
  return (
    <Card className="p-4">
      <Micro>{label}</Micro>
      <p className={`text-[28px] leading-none font-bold mt-2 tabular-nums ${tone ? tone.split(' ').find((c) => c.startsWith('text-')) : 'text-ink'}`}>
        {value}
      </p>
      <div className="mt-1.5 h-4">
        {delta !== undefined && <Delta value={delta ?? null} />}
        {raw !== undefined && raw !== 0 && (
          <span className={`text-[11px] font-semibold tabular-nums ${raw > 0 ? 'text-danger' : 'text-success'}`}>
            {raw > 0 ? '+' : ''}{raw} vs previous
          </span>
        )}
        {hint && <span className="text-[11px] text-faint">{hint}</span>}
      </div>
    </Card>
  );
}

/**
 * Leaderboard. Each row carries a proportional bar behind it so the shape of
 * the distribution — one dominant offender, or many even ones — reads before
 * any number is actually read.
 */
function Board({ title, rows, empty }: {
  title: string;
  rows: { label: string; value: string; weight: number; delta: React.ReactNode }[];
  empty?: string;
}) {
  const max = Math.max(...rows.map((r) => r.weight), 1);
  return (
    <Card className="p-4">
      <Micro>{title}</Micro>
      <div className="mt-2">
        {rows.length === 0 && <p className="text-xs text-faint py-2">{empty ?? 'Nothing to show.'}</p>}
        {rows.map((r) => (
          <div key={r.label} className="relative py-1.5 border-b border-black/[0.04] last:border-0">
            <div
              className="absolute inset-y-0.5 left-0 rounded-sm bg-brand/[0.07]"
              style={{ width: `${Math.max((r.weight / max) * 100, 1)}%` }}
              aria-hidden="true"
            />
            <div className="relative flex items-center justify-between gap-3 text-xs">
              <span className="truncate text-ink-soft">{r.label}</span>
              <span className="flex items-center gap-2 shrink-0">
                <span className="font-bold text-ink tabular-nums">{r.value}</span>
                <span className="w-12 text-right">{r.delta}</span>
              </span>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
