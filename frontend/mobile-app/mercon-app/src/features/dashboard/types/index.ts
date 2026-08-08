/**
 * Domain types for the Operator dashboard feature.
 * Mirrors the backend's Prisma models (Trip, Vehicle, Driver, Notification) —
 * see backend/api-server/prisma/schema.prisma for the source of truth.
 */

export type TripStatus =
  | 'Draft' | 'Dispatched' | 'AtPickup' | 'InTransit'
  | 'AtDelivery' | 'Completed' | 'Invoiced' | 'Cancelled';

export type DriverStatus = 'Available' | 'OnTrip' | 'OffDuty' | 'Inactive';

export type AssetStatus = 'Available' | 'OnTrip' | 'Maintenance' | 'Inactive';

export type AssetType = 'Flatbed' | 'Reefer' | 'Box' | 'Tanker';

export interface Kpi {
  value: number;
  delta: number | null;
}

export interface DashboardSummary {
  kpis: {
    total_trips: Kpi;
    active_drivers: Kpi;
    fleet_available: Kpi;
    fleet_on_trip: Kpi;
    revenue_this_month: Kpi;
    docs_expiring_soon: Kpi;
  };
  trip_status_distribution: Record<string, number>;
  monthly_revenue_chart: { month: string; revenue: number }[];
}

export interface DriverRef {
  id: string;
  first_name: string;
  last_name: string;
  status: DriverStatus;
}

export interface VehicleRef {
  id: string;
  ref_id: string | null;
  plate_number: string;
  asset_type: AssetType;
  status: AssetStatus;
  capacity_kg: number;
  last_lat: number | null;
  last_lng: number | null;
}

export interface CustomerRef {
  id: string;
  name: string;
}

export interface Trip {
  id: string;
  ref_id: string | null;
  status: TripStatus;
  cargo_type: string;
  planned_start: string | null;
  planned_end: string | null;
  actual_start: string | null;
  actual_end: string | null;
  createdAt: string;
  customer: CustomerRef | null;
  driver: DriverRef | null;
  vehicle: VehicleRef | null;
}

export interface Notification {
  id: string;
  title: string;
  message: string;
  type: string; // "Emergency" | "Trip" | "Document" | "System"
  is_read: boolean;
  entity_type: string | null;
  entity_id: string | null;
  createdAt: string;
}

export interface CurrentUser {
  id: string;
  username: string | null;
  name: string;
  email: string | null;
  phone: string | null;
  role: 'Admin' | 'Operator' | 'Driver';
}

/**
 * Display vocabulary for the Active Vehicles carousel's status pill — derived
 * from the real `TripStatus` / `AssetStatus` enums (see
 * `deriveVehicleCardStatus` in services/dashboardService.ts), not a new
 * backend enum.
 */
export type VehicleCardStatus =
  | 'En Route' | 'Loading' | 'Idle' | 'Maintenance' | 'Delivered' | 'Offline' | 'Delayed';

/** A vehicle currently attached to an active trip, joined with its driver — the shape the Active Vehicles carousel needs. */
export interface ActiveVehicleCard {
  tripId: string;
  tripStatus: TripStatus;
  cardStatus: VehicleCardStatus;
  driverName: string;
  driverInitials: string;
  driverOnline: boolean;
  originLabel: string;
  destinationLabel: string;
  truckId: string;
  assetType: AssetType;
  capacityKg: number;
  vehicleStatus: AssetStatus;
  lastLat: number | null;
  lastLng: number | null;
}

export type FleetPeriod = 'today' | 'week' | 'month';

export interface FleetCategoryUtilization {
  assetType: AssetType;
  totalTrucks: number;
  inUse: number;
  idle: number;
  maintenance: number;
  /** Share of this category's trucks that ran at least one trip in the selected period, 0-1. */
  utilization: number;
}

export interface FleetUtilization {
  categories: FleetCategoryUtilization[];
  totals: {
    totalTrucks: number;
    inUse: number;
    idle: number;
    maintenance: number;
    overallUtilization: number;
  };
}

/** Mirrors the backend's `DocType` enum (schema.prisma). */
export type DocType =
  | 'DriverLicense' | 'VehicleRegistration' | 'Insurance' | 'POD'
  | 'CustomsClearance' | 'Waybill' | 'Contract' | 'Invoice' | 'Emergency';

export interface DocumentRef {
  id: string;
  entity_type: string; // "Driver" | "Vehicle" | "Trip" | "MaintenanceRecord"
  entity_id: string;
  doc_type: DocType;
  expiry_date: string | null;
}

/**
 * The Document Expiry section's filter tabs. The backend has no "Company"
 * entity — it's derived here as "everything not tied to a Driver or
 * Vehicle" (Trip/MaintenanceRecord documents: contracts, invoices, customs
 * clearance, etc.), not a new backend concept.
 */
export type DocumentFilterScope = 'all' | 'vehicles' | 'drivers' | 'company';

export type ExpiryUrgency = 'valid' | 'expiringSoon' | 'expired';

/** A document with a real `expiry_date`, joined with its owning vehicle/driver for display. */
export interface DocumentExpiryEntry {
  id: string;
  docType: DocType;
  entityType: string;
  /** Vehicle plate number, driver name, or a generic fallback for company-level docs. */
  subjectLabel: string;
  expiryDate: string;
  /** Negative once expired. */
  daysLeft: number;
  urgency: ExpiryUrgency;
}

export interface DocumentExpirySummary {
  expiringSoon: number;
  expired: number;
  valid: number;
}
