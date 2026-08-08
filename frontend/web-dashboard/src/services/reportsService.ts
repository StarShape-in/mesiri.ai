import { api, ApiResponse } from '@/lib/api';

export interface ReportsSummary {
  kpis: {
    total_trips:        { value: number; delta: number | null };
    active_drivers:     { value: number; delta: null };
    fleet_available:    { value: number; delta: null };
    fleet_on_trip:      { value: number; delta: null };
    revenue_this_month: { value: number; delta: number | null };
    docs_expiring_soon: { value: number; delta: null };
  };
  trip_status_distribution: Record<string, number>;
  monthly_revenue_chart: { month: string; revenue: number }[];
}

export interface RevenueReport {
  monthly_breakdown: { month: string; revenue: number; count: number }[];
  total_all_time: number;
  outstanding_total: number;
  paid_invoice_count: number;
  avg_per_invoice: number;
  top_customers: { name: string; value: number }[];
}

export interface FleetPerfRow {
  id: string;
  ref_id: string | null;
  plate_number: string;
  status: string;
  total_trips: number;
  completed_trips: number;
  odometer: number | null;
  maintenance_cost: number;
}

export interface DriverPerfRow {
  id: string;
  ref_id: string | null;
  name: string;
  status: string;
  total_trips: number;
  completed_trips: number;
  ai_risk_score: number | null;
}

export interface PerformanceFilters {
  startDate?: string;
  endDate?: string;
  page?: number;
  per_page?: number;
}

export interface Paginated<T> {
  data: T[];
  meta: {
    total: number;
    page: number;
    limit: number;
    total_pages: number;
  };
}

export interface CustomReportFilters {
  startDate?: string;
  endDate?: string;
  customerId?: string;
}

export interface CustomReportData {
  kpis: {
    total_trips: number;
    total_revenue: number;
  };
  trip_status_distribution: Record<string, number>;
  trips: {
    id: string;
    ref_id: string;
    date: string;
    driver: string;
    driver_phone: string;
    vehicle: string;
    vehicle_type: string;
    carrier_name: string;
    customer: string;
    receiver: string;
    waiting_labor_charges: number;
    additional_stop_charges: number;
    billing_amount: number;
    total_amount: number;
    trip_charges: number;
    balance_amount: number;
    company_name: string;
    status: string;
    is_post_trip_settled: boolean;
  }[];
}

/* ─── Delay reporting ─────────────────────────────────────────────────────── */

/**
 * These three read every arrival in the range rather than a page of them, so
 * they scale with how much history the database holds - unlike the rest of the
 * app, where the client's 15s default is generous. Nginx allows 120s upstream;
 * this stays well inside that, so a slow answer still arrives instead of the
 * browser abandoning a request the server was about to complete.
 */
const DELAY_TIMEOUT_MS = 60_000;

export type DelayGranularity = 'day' | 'week' | 'month' | 'quarter' | 'year';
export type DelayDimension = 'route' | 'driver' | 'customer' | 'vehicle';

/** One filter set drives all three views, so choosing a company narrows the
 *  log, the grid and the analysis together rather than one at a time. */
export interface DelayFilters {
  startDate?: string;
  endDate?: string;
  customer_id?: string;
  driver_id?: string;
  vehicle_id?: string;
  reason?: string;
  needs_reason?: 'true';
  min_delay_hours?: number;
  page?: number;
  per_page?: number;
}

export interface DelayLogRow {
  stop_id: string;
  trip_id: string;
  trip_ref: string | null;
  date: string;
  stop_type: string;
  location: string;
  route: string;
  customer: string;
  driver: string;
  vehicle: string;
  planned_arrival: string;
  actual_arrival: string;
  delay_hours: number;
  dwell_hours: number | null;
  delay_reason: string | null;
  delay_note: string | null;
  needs_reason: boolean;
}

export interface DelayLogResponse {
  data: DelayLogRow[];
  meta: { total: number; page: number; limit: number; total_pages: number; truncated: boolean; threshold_minutes: number };
}

/** `pct: null` means nothing ran in that period — rendered blank, never 0%. */
export interface DelayGridCell { period: string; pct: number | null; total: number }

export interface DelayGrid {
  dimension: DelayDimension;
  granularity: DelayGranularity;
  periods: { key: string; label: string }[];
  all_rows: { label: string; cells: DelayGridCell[] };
  rows: { key: string; label: string; overall_pct: number | null; total: number; cells: DelayGridCell[] }[];
}

export interface DelayTotals {
  arrivals: number;
  delayed: number;
  on_time_pct: number | null;
  hours_lost: number;
  unexplained: number;
}

export interface DelayAnalysis {
  granularity: DelayGranularity;
  range: { start: string; end: string };
  previous_range: { start: string; end: string };
  totals: DelayTotals;
  previous_totals: DelayTotals;
  change: { hours_lost_pct: number | null; delayed_count: number };
  routes: { label: string; hours_lost: number; change_pct: number | null }[];
  drivers: { label: string; late: number; total: number; change: number }[];
  reasons: { reason: string; count: number; share_pct: number; change_pt: number }[];
  vehicles: { label: string; breakdowns: number; maintenance_cost: number; change: number }[];
  trend: { period: string; label: string; hours_lost: number }[];
}

export const reportsService = {
  async getDelayLog(filters?: DelayFilters): Promise<DelayLogResponse> {
    const res = await api.get('/reports/delays', { params: filters, timeout: DELAY_TIMEOUT_MS });
    return res.data as unknown as DelayLogResponse;
  },

  async getDelayGrid(
    filters?: DelayFilters & { dimension?: DelayDimension; granularity?: DelayGranularity },
  ): Promise<DelayGrid> {
    const res = await api.get<ApiResponse<DelayGrid>>('/reports/delays/grid', { params: filters, timeout: DELAY_TIMEOUT_MS });
    return res.data.data;
  },

  async getDelayAnalysis(
    filters?: DelayFilters & { granularity?: DelayGranularity },
  ): Promise<DelayAnalysis> {
    const res = await api.get<ApiResponse<DelayAnalysis>>('/reports/delays/analysis', { params: filters, timeout: DELAY_TIMEOUT_MS });
    return res.data.data;
  },

  async getSummary(): Promise<ReportsSummary> {
    const res = await api.get<ApiResponse<ReportsSummary>>('/reports/summary');
    return res.data.data;
  },

  async getFleetPerformance(filters?: PerformanceFilters): Promise<Paginated<FleetPerfRow>> {
    const res = await api.get<ApiResponse<Paginated<FleetPerfRow>>>('/reports/fleet', { params: filters });
    return res.data as unknown as Paginated<FleetPerfRow>; // Since the response format changed to {success, data, meta} which matches Paginated<T> after unpacking data
  },

  async getDriverPerformance(filters?: PerformanceFilters): Promise<Paginated<DriverPerfRow>> {
    const res = await api.get<ApiResponse<Paginated<DriverPerfRow>>>('/reports/drivers', { params: filters });
    return res.data as unknown as Paginated<DriverPerfRow>; // Same here
  },

  async getRevenueReport(months = 6): Promise<RevenueReport> {
    const res = await api.get<ApiResponse<RevenueReport>>('/reports/revenue', { params: { months } });
    return res.data.data;
  },

  async getCustomReport(filters: CustomReportFilters): Promise<CustomReportData> {
    const res = await api.get<ApiResponse<CustomReportData>>('/reports/custom', { params: filters });
    return res.data.data;
  },
};
