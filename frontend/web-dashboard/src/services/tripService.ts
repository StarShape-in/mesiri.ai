import { api, ApiResponse } from '@/lib/api';

export type TripStatus = 'Draft' | 'Dispatched' | 'AtPickup' | 'InTransit' | 'AtDelivery' | 'Completed' | 'Invoiced' | 'Cancelled';

export interface Trip {
  id: string;
  ref_id: string;
  status: TripStatus;
  cargo_type: string;
  planned_start: string | null;
  actual_start: string | null;
  planned_end: string | null;
  actual_end: string | null;
  planned_distance: number | null;
  extra_driver_payment: number | null;
  payment_reason: string | null;
  payment_status: string | null;
  waiting_labor_charges?: number;
  additional_stop_charges?: number;
  trip_charges?: number;
  billing_amount?: number;
  carrier_name?: string;
  is_post_trip_settled?: boolean;
  createdAt: string;
  customer?: { id: string; name: string; contact_phone: string };
  driver?: { id: string; ref_id: string; first_name: string; last_name: string; phone_primary: string; ai_risk_score?: number } | null;
  vehicle?: { id: string; ref_id: string; plate_number: string; asset_type: string } | null;
  stops?: TripStop[];
  invoices?: { id: string; ref_id: string; total_amount: number; status: string }[];
}

export interface TripStop {
  id: string;
  stop_sequence: number;
  stop_type: 'Pickup' | 'Dropoff' | 'Rest' | 'Refuel';
  location_lat: number;
  location_lng: number;
  location_name: string | null;
  planned_arrival: string | null;
  actual_arrival: string | null;
  actual_departure: string | null;
  delay_reason: DelayReason | null;
  delay_note: string | null;
  delay_logged_at: string | null;
}

export interface CreateTripPayload {
  customer_id: string;
  driver_id?: string;
  vehicle_id?: string;
  cargo_type?: string;
  planned_start?: string;
  stops: { stop_type: string; lat: number; lng: number; planned_arrival?: string; location_name?: string }[];
}

export const DELAY_REASONS = [
  'Traffic',
  'VehicleBreakdown',
  'CustomerNotReady',
  'SlowLoadingUnloading',
  'Weather',
  'Documentation',
  'RouteBlocked',
  'Other',
] as const;

export type DelayReason = (typeof DELAY_REASONS)[number];

/** Enum values are stored compactly; these are what an operator reads. */
export const DELAY_REASON_LABELS: Record<DelayReason, string> = {
  Traffic: 'Traffic',
  VehicleBreakdown: 'Vehicle breakdown',
  CustomerNotReady: 'Customer not ready',
  SlowLoadingUnloading: 'Slow loading / unloading',
  Weather: 'Weather',
  Documentation: 'Documentation',
  RouteBlocked: 'Route blocked',
  Other: 'Other',
};

export interface LogStopDelayPayload {
  delay_reason: DelayReason;
  delay_note?: string;
}

export interface TripFilters {
  status?: TripStatus;
  driver_id?: string;
  customer_id?: string;
  search?: string;
  date_filter?: string;
  start_date?: string;
  end_date?: string;
  page?: number;
  per_page?: number;
}

export interface UpdateTripFinancialsPayload {
  waiting_labor_charges?: number;
  additional_stop_charges?: number;
  trip_charges?: number;
  billing_amount?: number;
  carrier_name?: string;
  is_post_trip_settled?: boolean;
}

export const tripService = {
  async getAll(filters: TripFilters = {}): Promise<ApiResponse<Trip[]>> {
    const res = await api.get<ApiResponse<Trip[]>>('/trips', { params: filters });
    return res.data;
  },

  async getById(id: string): Promise<Trip> {
    const res = await api.get<ApiResponse<Trip>>(`/trips/${id}`);
    return res.data.data;
  },

  async getUnsettled(): Promise<Trip[]> {
    const res = await api.get<ApiResponse<Trip[]>>('/trips/unsettled');
    return res.data.data;
  },

  async create(payload: CreateTripPayload): Promise<Trip> {
    const res = await api.post<ApiResponse<Trip>>('/trips', payload);
    return res.data.data;
  },

  async updateStatus(id: string, status: TripStatus): Promise<Trip> {
    const res = await api.patch<ApiResponse<Trip>>(`/trips/${id}/status`, { status });
    return res.data.data;
  },

  async updateFinancials(id: string, payload: UpdateTripFinancialsPayload): Promise<Trip> {
    const res = await api.patch<ApiResponse<Trip>>(`/trips/${id}/financials`, payload);
    return res.data.data;
  },

  /** Record why a stop was reached late. Re-callable — a first guess often
   *  turns out to be something else once the driver is actually reached. */
  async logStopDelay(tripId: string, stopId: string, payload: LogStopDelayPayload): Promise<TripStop> {
    const res = await api.patch<ApiResponse<TripStop>>(`/trips/${tripId}/stops/${stopId}/delay`, payload);
    return res.data.data;
  },

  /** Assign a driver and/or vehicle to a trip that was created with "assign later". */
  async dispatch(id: string, payload: { driver_id?: string; vehicle_id?: string }): Promise<Trip> {
    const res = await api.post<ApiResponse<Trip>>(`/trips/${id}/dispatch`, payload);
    return res.data.data;
  },

  async approvePayment(id: string, amount: number, reason: string): Promise<Trip> {
    const res = await api.post<ApiResponse<Trip>>(`/trips/${id}/payment/approve`, { amount, reason });
    return res.data.data;
  },

  async bulkDelete(ids: string[]): Promise<void> {
    await api.post('/trips/bulk-delete', { ids });
  },

  async bulkUpdateStatus(ids: string[], status: string): Promise<void> {
    await api.post('/trips/bulk-update-status', { ids, status });
  },
};

