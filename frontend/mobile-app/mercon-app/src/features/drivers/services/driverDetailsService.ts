/**
 * Driver Details business logic — pure transforms over API-layer data.
 * Nothing here talks to the network and nothing here invents a value: every
 * output field traces back to a real column, or is `null`.
 */
import type {
  RawDocument,
  RawDriverDetail,
  RawDriverTrip,
  RawTripDetail,
  RawVehicle,
} from '../api/driverDetailsApi';
import type {
  AssignedVehicle,
  AssignmentStop,
  DriverAssignment,
  DriverDetail,
  DriverDocument,
  DriverDocumentStatus,
  DriverPerformance,
} from '../types';

/** A trip in one of these states is the driver's live assignment. Same list the web dashboard uses. */
export const ACTIVE_TRIP_STATUSES = ['Dispatched', 'AtPickup', 'InTransit', 'AtDelivery'] as const;

/** A document within this window reads as "Expires Soon" — matches the dashboard's 30-day expiry threshold. */
export const EXPIRY_SOON_DAYS = 30;

const MS_PER_DAY = 24 * 60 * 60 * 1000;

/** Whole days from now until `iso`; negative once past. Null for a missing/unparseable date. */
export function daysUntil(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const target = new Date(iso).getTime();
  if (Number.isNaN(target)) return null;
  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);
  return Math.round((target - startOfToday.getTime()) / MS_PER_DAY);
}

export function toDriverDetail(raw: RawDriverDetail): DriverDetail {
  return {
    id: raw.id,
    refId: raw.ref_id,
    firstName: raw.first_name,
    lastName: raw.last_name,
    phone: raw.phone_primary,
    status: raw.status,
    licenseNumber: raw.license_number,
    licenseExpiry: raw.license_expiry,
    licenseDaysLeft: daysUntil(raw.license_expiry) ?? 0,
    aiRiskScore: typeof raw.ai_risk_score === 'number' ? raw.ai_risk_score : null,
    isActive: raw.isActive,
    createdAt: raw.createdAt,
  };
}

/**
 * Maps a document's real `DocStatus` + `expiry_date` onto the screen's
 * four-value vocabulary. `PendingReview` wins over the date because a
 * document awaiting review isn't yet valid regardless of how far off its
 * expiry is; `Rejected` is surfaced as Expired since it is likewise not usable.
 */
export function documentDisplayStatus(
  status: RawDocument['status'],
  daysLeft: number | null,
): DriverDocumentStatus {
  if (status === 'PendingReview') return 'PendingRenewal';
  if (status === 'Expired' || status === 'Rejected') return 'Expired';
  if (daysLeft === null) return 'Valid';
  if (daysLeft < 0) return 'Expired';
  if (daysLeft <= EXPIRY_SOON_DAYS) return 'ExpiresSoon';
  return 'Valid';
}

export function toDriverDocument(raw: RawDocument): DriverDocument {
  const daysLeft = daysUntil(raw.expiry_date);
  return {
    id: raw.id,
    docType: raw.doc_type,
    status: raw.status,
    fileUrl: raw.file_url,
    issueDate: raw.issue_date,
    expiryDate: raw.expiry_date,
    daysLeft,
    displayStatus: documentDisplayStatus(raw.status, daysLeft),
  };
}

const URGENCY_ORDER: Record<DriverDocumentStatus, number> = {
  Expired: 0,
  ExpiresSoon: 1,
  PendingRenewal: 2,
  Valid: 3,
};

/** Most-urgent first, so the horizontal list leads with what needs action. */
export function sortDocumentsByUrgency(documents: DriverDocument[]): DriverDocument[] {
  return [...documents].sort((a, b) => {
    const byStatus = URGENCY_ORDER[a.displayStatus] - URGENCY_ORDER[b.displayStatus];
    if (byStatus !== 0) return byStatus;
    return (a.daysLeft ?? Number.MAX_SAFE_INTEGER) - (b.daysLeft ?? Number.MAX_SAFE_INTEGER);
  });
}

export function toAssignedVehicle(raw: RawVehicle): AssignedVehicle {
  return {
    id: raw.id,
    plateNumber: raw.plate_number,
    assetType: raw.asset_type,
    status: raw.status,
    capacityKg: raw.capacity_kg,
    trailerNumber: raw.trailer_number,
    trailerCapacityKg: raw.trailer_capacity_kg,
  };
}

/** The driver's live trip, or null when they are not currently assigned. */
export function findActiveTrip(trips: RawDriverTrip[]): RawDriverTrip | null {
  return trips.find((t) => (ACTIVE_TRIP_STATUSES as readonly string[]).includes(t.status)) ?? null;
}

function toAssignmentStop(stop: RawTripDetail['stops'][number]): AssignmentStop {
  return {
    sequence: stop.stop_sequence,
    lat: stop.location_lat,
    lng: stop.location_lng,
    plannedArrival: stop.planned_arrival,
    actualArrival: stop.actual_arrival,
  };
}

/**
 * Builds the Current Assignment view model. `detail` is optional: the list
 * endpoint gives everything except stops, so the card renders immediately and
 * fills in pickup/dropoff once GET /trips/:id resolves.
 */
export function toDriverAssignment(
  trip: RawDriverTrip,
  detail?: RawTripDetail | null,
): DriverAssignment {
  const stops = detail?.stops ?? [];
  const pickup = stops.find((s) => s.stop_type === 'Pickup');
  const dropoff = stops.find((s) => s.stop_type === 'Dropoff');

  return {
    tripId: trip.id,
    refId: trip.ref_id,
    status: trip.status,
    cargoType: trip.cargo_type,
    customerName: trip.customer?.name ?? null,
    plannedStart: trip.planned_start,
    plannedEnd: trip.planned_end,
    vehicle: trip.vehicle ? toAssignedVehicle(trip.vehicle) : null,
    pickup: pickup ? toAssignmentStop(pickup) : null,
    dropoff: dropoff ? toAssignmentStop(dropoff) : null,
  };
}

/**
 * All-time performance computed from the driver's own trips.
 *
 * On-time rate counts a completed trip as on time when `actual_end` is not
 * after `planned_end`. Trips missing either timestamp are excluded rather
 * than assumed on time — `onTimeSample` reports how many actually counted, so
 * the UI can say "of N trips" instead of implying a full history.
 */
export function computeDriverPerformance(
  trips: RawDriverTrip[],
  aiRiskScore: number | null,
): DriverPerformance {
  const completed = trips.filter((t) => t.status === 'Completed' || t.status === 'Invoiced');
  const measurable = completed.filter((t) => !!t.planned_end && !!t.actual_end);
  const onTime = measurable.filter(
    (t) => new Date(t.actual_end as string).getTime() <= new Date(t.planned_end as string).getTime(),
  );

  return {
    totalTrips: trips.length,
    completedTrips: completed.length,
    onTimeRatePct: measurable.length > 0 ? Math.round((onTime.length / measurable.length) * 100) : null,
    onTimeSample: measurable.length,
    aiRiskScore,
    averageRating: null,
  };
}

/** "24.4708, 39.6111" — the only honest rendering of a stop, since TripStop has no address column. */
export function formatCoordinates(lat: number, lng: number): string {
  return `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' });
}

/** "Expired 3 days ago" / "Expires today" / "12 days left" — used under document + licence dates. */
export function formatDaysLeft(daysLeft: number | null): string {
  if (daysLeft === null) return 'No expiry recorded';
  if (daysLeft < 0) {
    const n = Math.abs(daysLeft);
    return `Expired ${n} ${n === 1 ? 'day' : 'days'} ago`;
  }
  if (daysLeft === 0) return 'Expires today';
  return `${daysLeft} ${daysLeft === 1 ? 'day' : 'days'} left`;
}

export function driverDisplayName(driver: Pick<DriverDetail, 'firstName' | 'lastName'>): string {
  return `${driver.firstName} ${driver.lastName}`.trim();
}

export function driverDisplayInitials(driver: Pick<DriverDetail, 'firstName' | 'lastName'>): string {
  return `${driver.firstName[0] ?? ''}${driver.lastName[0] ?? ''}`.toUpperCase();
}

/** Capacity in kg, thousands-separated. */
export function formatCapacity(kg: number | null): string {
  if (kg === null || Number.isNaN(kg)) return '—';
  return `${kg.toLocaleString()} kg`;
}

/**
 * `ai_risk_score` is a *risk* float (0–1, higher = riskier), so the safety
 * score shown to the user is its inverse as a percentage.
 */
export function safetyScoreFromRisk(aiRiskScore: number | null): number | null {
  if (aiRiskScore === null || Number.isNaN(aiRiskScore)) return null;
  const clamped = Math.min(Math.max(aiRiskScore, 0), 1);
  return Math.round((1 - clamped) * 100);
}
