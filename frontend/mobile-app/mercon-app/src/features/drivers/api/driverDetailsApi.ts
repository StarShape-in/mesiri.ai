/**
 * Driver Details API layer — raw HTTP only. No business logic, no shape
 * transformation beyond unwrapping the `{ success, data, meta }` envelope.
 *
 * Endpoints used (all already exist; nothing here needs a backend change):
 *   GET   /drivers/:id                          → driver + its last 5 trips + its documents
 *   GET   /documents?entity_type=Driver&…       → the driver's documents, independently refreshable
 *   GET   /trips?driver_id=…                    → every trip for the driver, with vehicle + customer joined
 *   GET   /trips/:id                            → one trip with its stops (the only place stops are returned)
 *   PATCH /drivers/:id                          → status update
 *
 * All of these are gated to Admin/Operator by the backend RBAC, which matches
 * where this screen lives (the operator section of the app).
 */
import { api } from '@/lib/api';
import type { DocStatus, DriverStatus } from '../types';
import type { DocType } from '@/features/dashboard/types';
import type { StopType, TripStatus } from '@/lib/trips';

/** Raw driver row from GET /drivers/:id. `trips` is the last 5 by createdAt and carries no vehicle join. */
export interface RawDriverDetail {
  id: string;
  ref_id: string | null;
  first_name: string;
  last_name: string;
  phone_primary: string | null;
  status: DriverStatus;
  license_number: string;
  license_expiry: string;
  ai_risk_score: number | null;
  isActive: boolean;
  createdAt: string;
  documents?: RawDocument[];
}

export interface RawDocument {
  id: string;
  entity_type: string;
  entity_id: string;
  doc_type: DocType;
  status: DocStatus;
  file_url: string;
  issue_date: string | null;
  expiry_date: string | null;
}

export interface RawVehicle {
  id: string;
  plate_number: string;
  asset_type: 'Flatbed' | 'Reefer' | 'Box' | 'Tanker';
  status: 'Available' | 'OnTrip' | 'Maintenance' | 'Inactive';
  capacity_kg: number;
  trailer_number: string | null;
  trailer_capacity_kg: number | null;
}

/** Raw trip row from GET /trips?driver_id= — includes driver, vehicle and customer, but not stops. */
export interface RawDriverTrip {
  id: string;
  ref_id: string | null;
  status: TripStatus;
  cargo_type: string;
  planned_start: string | null;
  planned_end: string | null;
  actual_start: string | null;
  actual_end: string | null;
  createdAt: string;
  vehicle: RawVehicle | null;
  customer: { id: string; name: string } | null;
}

export interface RawTripStop {
  id: string;
  stop_sequence: number;
  stop_type: StopType;
  location_lat: number;
  location_lng: number;
  planned_arrival: string | null;
  actual_arrival: string | null;
}

/** Raw trip from GET /trips/:id — the only endpoint that returns `stops`. */
export interface RawTripDetail extends RawDriverTrip {
  stops: RawTripStop[];
}

export const driverDetailsApi = {
  async getDriver(driverId: string): Promise<RawDriverDetail> {
    const { data } = await api.get(`/drivers/${driverId}`);
    return data.data as RawDriverDetail;
  },

  async getDriverDocuments(driverId: string): Promise<RawDocument[]> {
    const { data } = await api.get('/documents', {
      params: { entity_type: 'Driver', entity_id: driverId },
    });
    return (data.data ?? []) as RawDocument[];
  },

  /**
   * Every trip for this driver. `per_page` is deliberately large: the
   * performance figures are all-time, and paging through them would mean the
   * on-time rate silently reflected only the newest page.
   */
  async getDriverTrips(driverId: string, perPage = 200): Promise<RawDriverTrip[]> {
    const { data } = await api.get('/trips', {
      params: { driver_id: driverId, per_page: perPage },
    });
    return (data.data ?? []) as RawDriverTrip[];
  },

  async getTripDetail(tripId: string): Promise<RawTripDetail> {
    const { data } = await api.get(`/trips/${tripId}`);
    return data.data as RawTripDetail;
  },

  async updateDriverStatus(driverId: string, status: DriverStatus): Promise<RawDriverDetail> {
    const { data } = await api.patch(`/drivers/${driverId}`, { status });
    return data.data as RawDriverDetail;
  },
};
