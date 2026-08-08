/**
 * Domain types for the Drivers feature.
 * Mirrors the backend's Driver/Trip/Vehicle Prisma models — see
 * backend/api-server/prisma/schema.prisma for the source of truth.
 */

export type DriverStatus = 'Available' | 'OnTrip' | 'OffDuty' | 'Inactive';

/**
 * Display vocabulary for DriverStatusBadge / DriverStatusIndicator. Only
 * the 4 `DriverStatus` values are ever produced by real data today —
 * `Suspended` / `OnLeave` aren't backend-tracked yet, but the color map
 * supports them so the badge is ready once they are (see CLAUDE.md Rule 0:
 * no invented enum values are ever *emitted*, only accepted for display).
 */
export type DriverDisplayStatus = DriverStatus | 'Suspended' | 'OnLeave';

export interface DriverActiveTrip {
  id: string;
  status: string;
  vehiclePlate: string | null;
}

export interface DriverListItem {
  id: string;
  ref_id: string | null;
  firstName: string;
  lastName: string;
  phone: string | null;
  status: DriverStatus;
  licenseNumber: string;
  licenseExpiry: string;
  createdAt: string;
  activeTrip: DriverActiveTrip | null;
  /** All-time trip count from GET /reports/drivers — null while that join hasn't resolved yet. */
  totalTrips: number | null;
  /**
   * The backend has no driver rating field (only `ai_risk_score`, a
   * different metric) — always null until one exists. DriverRating renders
   * "—" for null rather than a fabricated number.
   */
  rating: number | null;
}

export interface DriverListPage {
  drivers: DriverListItem[];
  meta: { page: number; per_page: number; total: number; total_pages: number };
}

export interface DriverStats {
  totalDrivers: number;
  online: number;
  onTrip: number;
  offline: number;
  /** Always 0 — `OnLeave` isn't a backend status yet. */
  onLeave: number;
  inactive: number;
}

export type DriverSortOption = 'name' | 'newest' | 'rating' | 'trips' | 'available' | 'online';

export interface DriverListParams {
  search?: string;
  status?: DriverStatus | null;
  page?: number;
  per_page?: number;
}

/* ─── Driver Details ──────────────────────────────────────────────────────
 * Everything below backs the Driver Details screen. Field-by-field these
 * mirror real columns in schema.prisma — where the screen design asked for
 * something the backend does not store (driver photo, star rating,
 * nationality, blood group, languages, years of experience, email), the
 * field is either absent here or typed `null` and rendered as "—". Nothing
 * is fabricated (CLAUDE.md Rule 0).
 */

/** Re-exported so the drivers feature has one import site; the enum mirror lives in the dashboard feature. */
export type { DocType } from '@/features/dashboard/types';

/** Mirrors the backend's `DocStatus` enum. */
export type DocStatus = 'PendingReview' | 'Verified' | 'Rejected' | 'Expired';

/** Mirrors the backend's `AssetStatus` enum. */
export type AssetStatus = 'Available' | 'OnTrip' | 'Maintenance' | 'Inactive';

/** Mirrors the backend's `AssetType` enum. */
export type AssetType = 'Flatbed' | 'Reefer' | 'Box' | 'Tanker';

/**
 * Display vocabulary for a driver document, derived from the document's real
 * `DocStatus` + `expiry_date` — see driverDetailsService.documentDisplayStatus.
 */
export type DriverDocumentStatus = 'Valid' | 'ExpiresSoon' | 'Expired' | 'PendingRenewal';

export interface DriverDocument {
  id: string;
  docType: import('@/features/dashboard/types').DocType;
  status: DocStatus;
  fileUrl: string;
  issueDate: string | null;
  expiryDate: string | null;
  /** Whole days until expiry; negative once expired, null when no expiry is recorded. */
  daysLeft: number | null;
  displayStatus: DriverDocumentStatus;
}

/**
 * A driver has no direct vehicle relation in the schema — a vehicle is
 * "assigned" only for as long as it is on the driver's active trip, which is
 * exactly how the web dashboard resolves it too.
 */
export interface AssignedVehicle {
  id: string;
  plateNumber: string;
  assetType: AssetType;
  status: AssetStatus;
  capacityKg: number;
  trailerNumber: string | null;
  trailerCapacityKg: number | null;
}

/**
 * TripStop stores only `location_lat`/`location_lng` — there is no address
 * text and no geocoder configured in this app, so origin/destination are
 * surfaced as real coordinates rather than invented place names (same policy
 * as driversService.driverLocationLabel).
 */
export interface AssignmentStop {
  sequence: number;
  lat: number;
  lng: number;
  plannedArrival: string | null;
  actualArrival: string | null;
}

export interface DriverAssignment {
  tripId: string;
  refId: string | null;
  status: import('@/lib/trips').TripStatus;
  cargoType: string;
  customerName: string | null;
  plannedStart: string | null;
  plannedEnd: string | null;
  vehicle: AssignedVehicle | null;
  pickup: AssignmentStop | null;
  dropoff: AssignmentStop | null;
}

export interface DriverPerformance {
  totalTrips: number;
  completedTrips: number;
  /** 0–100. Null when no completed trip carries both a planned and an actual end time. */
  onTimeRatePct: number | null;
  /** How many completed trips the on-time rate was computed from — shown so a 100% from 1 trip reads honestly. */
  onTimeSample: number;
  /** Backend `ai_risk_score` (0–1). Null when the driver has never been scored. */
  aiRiskScore: number | null;
  /** No rating column exists in the backend — always null, rendered as "—". */
  averageRating: number | null;
}

export interface DriverDetail {
  id: string;
  refId: string | null;
  firstName: string;
  lastName: string;
  phone: string | null;
  status: DriverStatus;
  licenseNumber: string;
  licenseExpiry: string;
  /** Whole days until the licence expires; negative once expired. */
  licenseDaysLeft: number;
  aiRiskScore: number | null;
  isActive: boolean;
  createdAt: string;
}
