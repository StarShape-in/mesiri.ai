/**
 * Delay reporting — the log, the on-time grid, and the analysis rollups.
 *
 * Kept out of reportsController because these three share a substantial amount
 * of loading and bucketing logic with each other and none with the fleet /
 * driver / revenue reports, and because that file is already large (the repo
 * caps source files around 1,000 lines).
 *
 * **Why the aggregation runs in JS rather than SQL.** "Late" is a comparison
 * between two columns (`actual_arrival` vs `planned_arrival`), which Prisma's
 * query builder cannot express in a `where`. The options were raw SQL for all
 * three endpoints or a bounded fetch aggregated in memory. At MERCON's volume
 * — a fleet measured in tens of trucks, so a year of stops is tens of
 * thousands of rows — the in-memory pass costs little and stays readable and
 * type-safe. `MAX_RECORDS` caps it, and responses report `truncated` rather
 * than silently returning a partial answer that looks complete. If the fleet
 * grows an order of magnitude, this is the file to move to SQL.
 */

import { Request, Response } from 'express';
import { DelayReason, StopType } from '@prisma/client';
import { prisma } from '../index';
import { logger } from '../utils/logger';
import { DELAY_THRESHOLD_MINUTES } from '../services/tripLifecycle';

/** Upper bound on stops pulled into memory for one report. */
const MAX_RECORDS = 20000;

type Granularity = 'day' | 'week' | 'month' | 'quarter' | 'year';
type Dimension = 'route' | 'driver' | 'customer' | 'vehicle';

/** One arrival that had a schedule to be judged against. */
interface DelayRecord {
  stopId: string;
  tripId: string;
  tripRef: string | null;
  stopType: StopType;
  arrivedAt: Date;
  plannedAt: Date;
  delayMinutes: number;
  isLate: boolean;
  dwellMinutes: number | null;
  routeLabel: string;
  customerId: string | null;
  customerName: string;
  driverId: string | null;
  driverName: string;
  vehicleId: string | null;
  vehiclePlate: string;
  reason: DelayReason | null;
  reasonNote: string | null;
  locationName: string;
}

// --- period helpers ---------------------------------------------------------

function startOfWeek(d: Date): Date {
  const out = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
  // Monday-based: the working week a dispatcher actually plans around.
  const shift = (out.getUTCDay() + 6) % 7;
  out.setUTCDate(out.getUTCDate() - shift);
  return out;
}

/** Sortable bucket key + the label the UI column header shows. */
function periodOf(date: Date, g: Granularity): { key: string; label: string } {
  const y = date.getUTCFullYear();
  const m = date.getUTCMonth();
  switch (g) {
    case 'day': {
      const key = date.toISOString().slice(0, 10);
      return { key, label: key.slice(5) };
    }
    case 'week': {
      const s = startOfWeek(date);
      return { key: s.toISOString().slice(0, 10), label: `wk ${s.toISOString().slice(5, 10)}` };
    }
    case 'quarter': {
      const q = Math.floor(m / 3) + 1;
      return { key: `${y}-Q${q}`, label: `Q${q} ${y}` };
    }
    case 'year':
      return { key: String(y), label: String(y) };
    case 'month':
    default: {
      const key = `${y}-${String(m + 1).padStart(2, '0')}`;
      const label = date.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' }) + ` ${y}`;
      return { key, label };
    }
  }
}

/** The window immediately before [start, end], same length — what deltas compare against. */
function previousWindow(start: Date, end: Date): { start: Date; end: Date } {
  const span = end.getTime() - start.getTime();
  return { start: new Date(start.getTime() - span), end: new Date(start.getTime() - 1) };
}

function parseRange(q: any): { start: Date; end: Date } {
  const end = q.endDate && !isNaN(Date.parse(q.endDate)) ? new Date(q.endDate) : new Date();
  end.setHours(23, 59, 59, 999);
  let start: Date;
  if (q.startDate && !isNaN(Date.parse(q.startDate))) {
    start = new Date(q.startDate);
  } else {
    // A month back by default: long enough to be useful, short enough that an
    // unfiltered request never scans a year.
    start = new Date(end);
    start.setMonth(start.getMonth() - 1);
  }
  start.setHours(0, 0, 0, 0);
  return { start, end };
}

function asGranularity(v: any): Granularity {
  return ['day', 'week', 'month', 'quarter', 'year'].includes(v) ? v : 'month';
}

function asDimension(v: any): Dimension {
  return ['route', 'driver', 'customer', 'vehicle'].includes(v) ? v : 'route';
}

// --- loading ----------------------------------------------------------------

function stopName(s: { location_name: string | null; location_lat: number; location_lng: number }): string {
  // Falls back to coordinates so trips created before stops had names still
  // appear, rather than collapsing into a single blank row.
  return s.location_name?.trim() || `${s.location_lat.toFixed(4)}, ${s.location_lng.toFixed(4)}`;
}

async function loadRecords(
  q: any,
  start: Date,
  end: Date,
): Promise<{ records: DelayRecord[]; truncated: boolean }> {
  const stops = await prisma.tripStop.findMany({
    where: {
      deletedAt: null,
      planned_arrival: { not: null },
      actual_arrival: { gte: start, lte: end },
      ...(q.reason && q.reason in DelayReason ? { delay_reason: q.reason as DelayReason } : {}),
      trip: {
        deletedAt: null,
        ...(q.customer_id ? { customerId: String(q.customer_id) } : {}),
        ...(q.driver_id ? { driverId: String(q.driver_id) } : {}),
        ...(q.vehicle_id ? { vehicleId: String(q.vehicle_id) } : {}),
      },
    },
    // `select`, not `include`. A trip carries cargo details, pricing, POD
    // fields and timestamps this report never reads, and `include` fetches
    // every one of them — for each stop, so twice per trip. On a database with
    // a couple of years of history that is megabytes of unread columns and the
    // difference between the grid answering and the browser timing out.
    select: {
      id: true,
      stop_type: true,
      actual_arrival: true,
      planned_arrival: true,
      actual_departure: true,
      location_name: true,
      location_lat: true,
      location_lng: true,
      delay_reason: true,
      delay_note: true,
      trip: {
        select: {
          id: true,
          ref_id: true,
          customer: { select: { id: true, name: true } },
          driver: { select: { id: true, first_name: true, last_name: true } },
          vehicle: { select: { id: true, plate_number: true } },
          stops: {
            select: { stop_type: true, location_name: true, location_lat: true, location_lng: true },
            orderBy: { stop_sequence: 'asc' },
          },
        },
      },
    },
    orderBy: { actual_arrival: 'desc' },
    take: MAX_RECORDS + 1,
  });

  const truncated = stops.length > MAX_RECORDS;
  const rows = truncated ? stops.slice(0, MAX_RECORDS) : stops;

  const records: DelayRecord[] = rows.map((s) => {
    const trip = s.trip;
    const pickup = trip.stops.find((x) => x.stop_type === StopType.Pickup);
    const dropoff = trip.stops.find((x) => x.stop_type === StopType.Dropoff);
    const routeLabel =
      pickup && dropoff ? `${stopName(pickup)} → ${stopName(dropoff)}` : 'Unknown route';

    const delayMinutes = Math.round(
      (s.actual_arrival!.getTime() - s.planned_arrival!.getTime()) / 60000,
    );
    const dwellMinutes = s.actual_departure
      ? Math.round((s.actual_departure.getTime() - s.actual_arrival!.getTime()) / 60000)
      : null;

    return {
      stopId: s.id,
      tripId: trip.id,
      tripRef: trip.ref_id,
      stopType: s.stop_type,
      arrivedAt: s.actual_arrival!,
      plannedAt: s.planned_arrival!,
      delayMinutes,
      isLate: delayMinutes >= DELAY_THRESHOLD_MINUTES,
      dwellMinutes,
      routeLabel,
      customerId: trip.customer?.id ?? null,
      customerName: trip.customer?.name ?? 'Unknown customer',
      driverId: trip.driver?.id ?? null,
      driverName: trip.driver ? `${trip.driver.first_name} ${trip.driver.last_name}` : 'Unassigned',
      vehicleId: trip.vehicle?.id ?? null,
      vehiclePlate: trip.vehicle?.plate_number ?? 'Unassigned',
      reason: s.delay_reason,
      reasonNote: s.delay_note,
      locationName: stopName(s),
    };
  });

  return { records, truncated };
}

function dimensionKey(r: DelayRecord, d: Dimension): { key: string; label: string } {
  switch (d) {
    case 'driver': return { key: r.driverId ?? 'unassigned', label: r.driverName };
    case 'customer': return { key: r.customerId ?? 'unknown', label: r.customerName };
    case 'vehicle': return { key: r.vehicleId ?? 'unassigned', label: r.vehiclePlate };
    case 'route':
    default: return { key: r.routeLabel, label: r.routeLabel };
  }
}

const hours = (minutes: number) => Math.round((minutes / 60) * 100) / 100;

// --- 1. the log -------------------------------------------------------------

/**
 * Every late arrival in the window, one row each — the detail sheet. Only late
 * stops are listed; on-time ones are still loaded because the grid's
 * percentages need them as the denominator.
 */
export const getDelayLog = async (req: Request, res: Response) => {
  try {
    const { start, end } = parseRange(req.query);
    const { records, truncated } = await loadRecords(req.query, start, end);

    const minDelay = Number(req.query.min_delay_hours);
    const late = records
      .filter((r) => r.isLate)
      .filter((r) => (Number.isFinite(minDelay) ? r.delayMinutes >= minDelay * 60 : true))
      .filter((r) => (req.query.needs_reason === 'true' ? r.reason === null : true));

    const page = Math.max(parseInt(String(req.query.page ?? '1'), 10) || 1, 1);
    const perPage = Math.min(Math.max(parseInt(String(req.query.per_page ?? '25'), 10) || 25, 1), 200);
    const slice = late.slice((page - 1) * perPage, page * perPage);

    res.json({
      success: true,
      data: slice.map((r) => ({
        stop_id: r.stopId,
        trip_id: r.tripId,
        trip_ref: r.tripRef,
        date: r.arrivedAt,
        stop_type: r.stopType,
        location: r.locationName,
        route: r.routeLabel,
        customer: r.customerName,
        driver: r.driverName,
        vehicle: r.vehiclePlate,
        planned_arrival: r.plannedAt,
        actual_arrival: r.arrivedAt,
        delay_hours: hours(r.delayMinutes),
        dwell_hours: r.dwellMinutes === null ? null : hours(r.dwellMinutes),
        delay_reason: r.reason,
        delay_note: r.reasonNote,
        needs_reason: r.reason === null,
      })),
      meta: {
        total: late.length,
        page,
        limit: perPage,
        total_pages: Math.ceil(late.length / perPage),
        truncated,
        threshold_minutes: DELAY_THRESHOLD_MINUTES,
      },
    });
  } catch (error) {
    logger.error({ err: error }, 'Failed to build delay log');
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to build delay report' } });
  }
};

// --- 2. the on-time grid ----------------------------------------------------

/**
 * On-time percentage as rows × periods. The dimension switch is what lets one
 * grid answer "which route slips", "which driver slips" and "which customer
 * are we failing" without three separate screens.
 */
export const getDelayGrid = async (req: Request, res: Response) => {
  try {
    const { start, end } = parseRange(req.query);
    const granularity = asGranularity(req.query.granularity);
    const dimension = asDimension(req.query.dimension);
    const { records, truncated } = await loadRecords(req.query, start, end);

    const periods = new Map<string, string>();
    const rows = new Map<string, { label: string; cells: Map<string, { total: number; onTime: number }> }>();
    const overall = new Map<string, { total: number; onTime: number }>();

    for (const r of records) {
      const p = periodOf(r.arrivedAt, granularity);
      periods.set(p.key, p.label);

      const d = dimensionKey(r, dimension);
      if (!rows.has(d.key)) rows.set(d.key, { label: d.label, cells: new Map() });
      const row = rows.get(d.key)!;
      const cell = row.cells.get(p.key) ?? { total: 0, onTime: 0 };
      cell.total += 1;
      if (!r.isLate) cell.onTime += 1;
      row.cells.set(p.key, cell);

      const all = overall.get(p.key) ?? { total: 0, onTime: 0 };
      all.total += 1;
      if (!r.isLate) all.onTime += 1;
      overall.set(p.key, all);
    }

    // Newest first, matching how the reference sheet is read.
    const periodKeys = [...periods.keys()].sort().reverse();
    const pct = (c: { total: number; onTime: number }) =>
      c.total === 0 ? null : Math.round((c.onTime / c.total) * 1000) / 10;

    const rowOut = [...rows.entries()]
      .map(([key, row]) => {
        const totals = [...row.cells.values()].reduce(
          (a, c) => ({ total: a.total + c.total, onTime: a.onTime + c.onTime }),
          { total: 0, onTime: 0 },
        );
        return {
          key,
          label: row.label,
          overall_pct: pct(totals),
          total: totals.total,
          // null (not 0%) where nothing ran — an empty cell and a total
          // failure must not look the same.
          cells: periodKeys.map((pk) => {
            const c = row.cells.get(pk);
            return { period: pk, pct: c ? pct(c) : null, total: c?.total ?? 0 };
          }),
        };
      })
      .sort((a, b) => (a.overall_pct ?? 101) - (b.overall_pct ?? 101));

    res.json({
      success: true,
      data: {
        dimension,
        granularity,
        periods: periodKeys.map((k) => ({ key: k, label: periods.get(k)! })),
        all_rows: {
          label: 'All',
          cells: periodKeys.map((pk) => {
            const c = overall.get(pk);
            return { period: pk, pct: c ? pct(c) : null, total: c?.total ?? 0 };
          }),
        },
        rows: rowOut,
      },
      meta: { truncated, threshold_minutes: DELAY_THRESHOLD_MINUTES },
    });
  } catch (error) {
    logger.error({ err: error }, 'Failed to build delay grid');
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to build delay grid' } });
  }
};

// --- 3. the analysis --------------------------------------------------------

function summarise(records: DelayRecord[]) {
  const late = records.filter((r) => r.isLate);
  const hoursLost = late.reduce((a, r) => a + r.delayMinutes, 0);

  const byRoute = new Map<string, number>();
  const byDriver = new Map<string, { label: string; late: number; total: number }>();
  const byReason = new Map<string, number>();
  const byVehicle = new Map<string, { label: string; breakdowns: number }>();

  for (const r of records) {
    const d = byDriver.get(r.driverId ?? 'unassigned') ?? { label: r.driverName, late: 0, total: 0 };
    d.total += 1;
    if (r.isLate) d.late += 1;
    byDriver.set(r.driverId ?? 'unassigned', d);
  }
  for (const r of late) {
    byRoute.set(r.routeLabel, (byRoute.get(r.routeLabel) ?? 0) + r.delayMinutes);
    // Unexplained is counted as its own bucket rather than dropped — "how much
    // do we not know" is itself a number worth watching.
    const reasonKey = r.reason ?? 'Unrecorded';
    byReason.set(reasonKey, (byReason.get(reasonKey) ?? 0) + 1);
    if (r.reason === DelayReason.VehicleBreakdown) {
      const v = byVehicle.get(r.vehicleId ?? 'unassigned') ?? { label: r.vehiclePlate, breakdowns: 0 };
      v.breakdowns += 1;
      byVehicle.set(r.vehicleId ?? 'unassigned', v);
    }
  }

  return {
    totals: {
      arrivals: records.length,
      delayed: late.length,
      on_time_pct: records.length ? Math.round(((records.length - late.length) / records.length) * 1000) / 10 : null,
      hours_lost: hours(hoursLost),
      unexplained: late.filter((r) => r.reason === null).length,
    },
    byRoute,
    byDriver,
    byReason,
    byVehicle,
    lateCount: late.length,
  };
}

/**
 * Leaderboards and trend for any period, each figure paired with the same
 * figure from the window immediately before it. A total says a route lost 14
 * hours; the delta says it is getting worse, which is the part that can still
 * be acted on.
 */
export const getDelayAnalysis = async (req: Request, res: Response) => {
  try {
    const { start, end } = parseRange(req.query);
    const granularity = asGranularity(req.query.granularity);
    const prev = previousWindow(start, end);

    const [current, previous] = await Promise.all([
      loadRecords(req.query, start, end),
      loadRecords(req.query, prev.start, prev.end),
    ]);

    const now = summarise(current.records);
    const before = summarise(previous.records);

    const delta = (a: number, b: number) => (b === 0 ? null : Math.round(((a - b) / b) * 1000) / 10);

    const routes = [...now.byRoute.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
      .map(([label, mins]) => ({
        label,
        hours_lost: hours(mins),
        change_pct: delta(mins, before.byRoute.get(label) ?? 0),
      }));

    const drivers = [...now.byDriver.entries()]
      .filter(([, d]) => d.late > 0)
      .sort((a, b) => b[1].late - a[1].late)
      .slice(0, 8)
      .map(([key, d]) => ({
        label: d.label,
        late: d.late,
        total: d.total,
        change: d.late - (before.byDriver.get(key)?.late ?? 0),
      }));

    const reasons = [...now.byReason.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([reason, count]) => {
        const share = now.lateCount ? Math.round((count / now.lateCount) * 1000) / 10 : 0;
        const beforeShare = before.lateCount
          ? Math.round(((before.byReason.get(reason) ?? 0) / before.lateCount) * 1000) / 10
          : 0;
        return { reason, count, share_pct: share, change_pt: Math.round((share - beforeShare) * 10) / 10 };
      });

    // Repair spend comes from maintenance records, not from delays — the two
    // together are what "which truck is costing us" actually means.
    const maintenance = await prisma.maintenanceRecord.groupBy({
      by: ['vehicleId'],
      where: { deletedAt: null, service_date: { gte: start, lte: end } },
      _sum: { cost: true },
      _count: { _all: true },
    });
    const costByVehicle = new Map(maintenance.map((m) => [m.vehicleId, m._sum.cost ?? 0]));

    const vehicles = [...now.byVehicle.entries()]
      .sort((a, b) => b[1].breakdowns - a[1].breakdowns)
      .slice(0, 8)
      .map(([key, v]) => ({
        label: v.label,
        breakdowns: v.breakdowns,
        maintenance_cost: costByVehicle.get(key) ?? 0,
        change: v.breakdowns - (before.byVehicle.get(key)?.breakdowns ?? 0),
      }));

    // Trend spans the current window only; the previous window feeds the
    // headline delta, not the bars.
    const trendMap = new Map<string, { label: string; minutes: number }>();
    for (const r of current.records.filter((x) => x.isLate)) {
      const p = periodOf(r.arrivedAt, granularity);
      const t = trendMap.get(p.key) ?? { label: p.label, minutes: 0 };
      t.minutes += r.delayMinutes;
      trendMap.set(p.key, t);
    }
    const trend = [...trendMap.entries()]
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([key, t]) => ({ period: key, label: t.label, hours_lost: hours(t.minutes) }));

    res.json({
      success: true,
      data: {
        granularity,
        range: { start, end },
        previous_range: { start: prev.start, end: prev.end },
        totals: now.totals,
        previous_totals: before.totals,
        change: {
          hours_lost_pct: delta(now.totals.hours_lost, before.totals.hours_lost),
          delayed_count: now.totals.delayed - before.totals.delayed,
        },
        routes,
        drivers,
        reasons,
        vehicles,
        trend,
      },
      meta: {
        truncated: current.truncated || previous.truncated,
        threshold_minutes: DELAY_THRESHOLD_MINUTES,
      },
    });
  } catch (error) {
    logger.error({ err: error }, 'Failed to build delay analysis');
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: 'Failed to build delay analysis' } });
  }
};
