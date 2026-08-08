/**
 * Driver trip API — talks to the mobile trip endpoints.
 *   GET  /mobile/trips/current      → the driver's active trip (or null)
 *   POST /mobile/trips/:id/status   → advance the trip's status
 */
import { api } from './api';

export type TripStatus =
  | 'Draft' | 'Dispatched' | 'AtPickup' | 'InTransit'
  | 'AtDelivery' | 'Completed' | 'Invoiced' | 'Cancelled';

export type StopType = 'Pickup' | 'Dropoff' | 'Rest' | 'Refuel';

export interface TripStop {
  id: string;
  stop_sequence: number;
  stop_type: StopType;
  location_lat: number;
  location_lng: number;
}

export interface MobileTrip {
  id: string;
  ref_id: string | null;
  status: TripStatus;
  cargo_type: string;
  planned_distance: number | null;
  planned_start?: string | null;
  actual_start?: string | null;
  planned_end: string | null;
  actual_end?: string | null;
  customer?: { id: string; name: string } | null;
  vehicle?: { id: string; plate_number: string } | null;
  stops: TripStop[];
}

export const tripService = {
  async getCurrent(): Promise<MobileTrip | null> {
    const { data } = await api.get('/mobile/trips/current');
    return data.data as MobileTrip | null;
  },

  /** Past trips (completed / invoiced / cancelled), newest first. */
  async getHistory(limit = 30): Promise<MobileTrip[]> {
    const { data } = await api.get('/mobile/trips/history', { params: { limit } });
    return (data.data ?? []) as MobileTrip[];
  },

  async updateStatus(id: string, status: TripStatus): Promise<MobileTrip> {
    const { data } = await api.post(`/mobile/trips/${id}/status`, { status });
    return data.data as MobileTrip;
  },

  /** Upload a cargo (pickup) or POD (delivery) photo and attach it to the trip. */
  async uploadPhoto(
    id: string,
    kind: 'cargo' | 'pod',
    asset: { uri: string; mimeType?: string | null; fileName?: string | null },
  ): Promise<void> {
    const form = new FormData();
    form.append('file', {
      uri: asset.uri,
      name: asset.fileName ?? `${kind}.jpg`,
      type: asset.mimeType ?? 'image/jpeg',
      // React Native's FormData file shape isn't in the DOM lib types.
    } as unknown as Blob);
    form.append('kind', kind);
    // Don't set Content-Type manually — axios/RN needs to generate it
    // itself so it includes the multipart boundary. A hardcoded header
    // here strips the boundary and the backend fails to parse the body.
    await api.post(`/mobile/trips/${id}/photo`, form);
  },
};

/** Which transitions require a photo first (business rules BR-006 / BR-009). */
export const PHOTO_FOR: Partial<Record<TripStatus, 'cargo' | 'pod'>> = {
  InTransit: 'cargo', // cargo photo required before moving to In Transit
  Completed: 'pod',   // POD photo required before completing
};

/** The next step a driver can take from the current status (null = nothing to do). */
export const NEXT_STEP: Partial<Record<TripStatus, { to: TripStatus; label: string }>> = {
  Dispatched: { to: 'AtPickup',   label: 'Arrived at Pickup' },
  AtPickup:   { to: 'InTransit',  label: 'Start Trip (Picked Up)' },
  InTransit:  { to: 'AtDelivery', label: 'View Live Map' },
  AtDelivery: { to: 'Completed',  label: 'Complete Delivery' },
};

/** Human-friendly label for a status. */
export function statusLabel(s: TripStatus): string {
  switch (s) {
    case 'AtPickup': return 'At Pickup';
    case 'InTransit': return 'In Transit';
    case 'AtDelivery': return 'At Delivery';
    default: return s;
  }
}
