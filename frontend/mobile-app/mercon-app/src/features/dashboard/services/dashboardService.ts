/**
 * Dashboard business logic — pure transforms over API-layer data. Nothing
 * here talks to the network; hooks call the api layer, then hand the raw
 * response through these functions.
 */
import type {
  ActiveVehicleCard, AssetStatus, AssetType, DocumentExpiryEntry, DocumentExpirySummary,
  DocumentFilterScope, DocumentRef, DriverRef, ExpiryUrgency, FleetCategoryUtilization, FleetPeriod,
  FleetUtilization, Trip, TripStatus, VehicleCardStatus, VehicleRef,
} from '../types';
import type { FleetTripCount } from '../api/dashboardApi';

export const ACTIVE_TRIP_STATUSES: Trip['status'][] = ['Dispatched', 'AtPickup', 'InTransit', 'AtDelivery'];
const OPEN_TRIP_STATUSES: Trip['status'][] = ['Draft', ...ACTIVE_TRIP_STATUSES];
const ASSET_TYPES: AssetType[] = ['Flatbed', 'Reefer', 'Box', 'Tanker'];

export function filterActiveTrips(trips: Trip[]): Trip[] {
  return trips.filter((t) => ACTIVE_TRIP_STATUSES.includes(t.status));
}

/**
 * A trip is "delayed" when its planned arrival has passed and it hasn't
 * reached delivery/completion yet. There's no `Delayed` trip status in the
 * backend enum, so this is derived from `planned_end` vs. now rather than a
 * status flag.
 */
export function filterDelayedDeliveries(trips: Trip[]): Trip[] {
  const now = Date.now();
  return trips.filter((t) => {
    if (!OPEN_TRIP_STATUSES.includes(t.status)) return false;
    if (!t.planned_end) return false;
    return new Date(t.planned_end).getTime() < now;
  });
}

export function initialsOf(firstName: string, lastName: string): string {
  return `${firstName[0] ?? ''}${lastName[0] ?? ''}`.toUpperCase();
}

/**
 * Maps the real trip/vehicle status enums onto the Active Vehicles card's
 * display vocabulary. "Delayed" isn't a backend status — it wins over the
 * trip status whenever the delivery is running late (see
 * `filterDelayedDeliveries`).
 */
export function deriveVehicleCardStatus(tripStatus: TripStatus, vehicleStatus: AssetStatus, isDelayed: boolean): VehicleCardStatus {
  if (isDelayed) return 'Delayed';
  switch (tripStatus) {
    case 'Dispatched':
    case 'AtPickup':
      return 'Loading';
    case 'InTransit':
    case 'AtDelivery':
      return 'En Route';
    case 'Completed':
    case 'Invoiced':
      return 'Delivered';
    default:
      break;
  }
  if (vehicleStatus === 'Maintenance') return 'Maintenance';
  if (vehicleStatus === 'Inactive') return 'Offline';
  return 'Idle';
}

/** Vehicles currently out on an active trip, joined with their driver, for the Active Vehicles carousel. */
export function buildActiveVehicleCards(trips: Trip[]): ActiveVehicleCard[] {
  return filterActiveTrips(trips)
    .filter((t) => t.vehicle && t.driver)
    .map((t) => {
      const isDelayed = !!t.planned_end && new Date(t.planned_end).getTime() < Date.now();
      return {
        tripId: t.id,
        tripStatus: t.status,
        cardStatus: deriveVehicleCardStatus(t.status, t.vehicle!.status, isDelayed),
        driverName: `${t.driver!.first_name} ${t.driver!.last_name}`,
        driverInitials: initialsOf(t.driver!.first_name, t.driver!.last_name),
        driverOnline: t.driver!.status === 'OnTrip',
        originLabel: t.cargo_type,
        destinationLabel: t.customer?.name ?? 'Customer',
        truckId: t.vehicle!.ref_id ?? t.vehicle!.plate_number,
        assetType: t.vehicle!.asset_type,
        capacityKg: t.vehicle!.capacity_kg,
        vehicleStatus: t.vehicle!.status,
        lastLat: t.vehicle!.last_lat,
        lastLng: t.vehicle!.last_lng,
      };
    });
}

/** Start/end ISO bounds for a fleet-utilization period tab. */
export function periodRange(period: FleetPeriod): { startDate: string; endDate: string } {
  const now = new Date();
  const endDate = now.toISOString();
  const start = new Date(now);
  if (period === 'today') {
    start.setHours(0, 0, 0, 0);
  } else if (period === 'week') {
    start.setDate(start.getDate() - 7);
  } else {
    start.setMonth(start.getMonth() - 1);
  }
  return { startDate: start.toISOString(), endDate };
}

/**
 * Groups vehicles by asset type into In Use / Idle / Maintenance (from their
 * current status — the backend doesn't track status history), and pairs
 * each category with its share of trucks that ran a trip in `tripCounts`'
 * date window, as the period-scoped utilization figure.
 */
export function buildFleetUtilization(vehicles: VehicleRef[], tripCounts: FleetTripCount[]): FleetUtilization {
  const tripsById = new Map(tripCounts.map((v) => [v.id, v.total_trips]));

  const categories: FleetCategoryUtilization[] = ASSET_TYPES.map((assetType) => {
    const inCategory = vehicles.filter((v) => v.asset_type === assetType);
    const inUse = inCategory.filter((v) => v.status === 'OnTrip').length;
    const idle = inCategory.filter((v) => v.status === 'Available').length;
    const maintenance = inCategory.filter((v) => v.status === 'Maintenance').length;
    const activeInPeriod = inCategory.filter((v) => (tripsById.get(v.id) ?? 0) > 0).length;
    return {
      assetType,
      totalTrucks: inCategory.length,
      inUse,
      idle,
      maintenance,
      utilization: inCategory.length > 0 ? activeInPeriod / inCategory.length : 0,
    };
  }).filter((c) => c.totalTrucks > 0);

  const totals = categories.reduce(
    (acc, c) => ({
      totalTrucks: acc.totalTrucks + c.totalTrucks,
      inUse: acc.inUse + c.inUse,
      idle: acc.idle + c.idle,
      maintenance: acc.maintenance + c.maintenance,
      overallUtilization: 0,
    }),
    { totalTrucks: 0, inUse: 0, idle: 0, maintenance: 0, overallUtilization: 0 },
  );
  totals.overallUtilization = totals.totalTrucks > 0 ? totals.inUse / totals.totalTrucks : 0;

  return { categories, totals };
}

const EXPIRING_SOON_WINDOW_DAYS = 30;

/** Whole days until `dateIso` — negative once it's passed. */
export function daysUntil(dateIso: string): number {
  const ms = new Date(dateIso).getTime() - Date.now();
  return Math.ceil(ms / (1000 * 60 * 60 * 24));
}

export function urgencyOf(daysLeft: number): ExpiryUrgency {
  if (daysLeft < 0) return 'expired';
  if (daysLeft <= EXPIRING_SOON_WINDOW_DAYS) return 'expiringSoon';
  return 'valid';
}

/** "Company" has no backend entity — it means "not tied to a Driver or Vehicle" (Trip/MaintenanceRecord docs). */
export function matchesDocumentScope(entityType: string, scope: DocumentFilterScope): boolean {
  if (scope === 'all') return true;
  if (scope === 'vehicles') return entityType === 'Vehicle';
  if (scope === 'drivers') return entityType === 'Driver';
  return entityType !== 'Vehicle' && entityType !== 'Driver';
}

/**
 * Joins documents that carry an expiry date with their owning vehicle/driver
 * (for display), scoped to the selected filter tab, sorted most-urgent
 * first (soonest/most-overdue expiry first).
 */
export function buildDocumentExpiryEntries(
  documents: DocumentRef[], vehicles: VehicleRef[], drivers: DriverRef[], scope: DocumentFilterScope,
): DocumentExpiryEntry[] {
  const vehicleById = new Map(vehicles.map((v) => [v.id, v]));
  const driverById = new Map(drivers.map((d) => [d.id, d]));

  return documents
    .filter((d): d is DocumentRef & { expiry_date: string } => !!d.expiry_date)
    .filter((d) => matchesDocumentScope(d.entity_type, scope))
    .map((d) => {
      const daysLeft = daysUntil(d.expiry_date);
      let subjectLabel = d.entity_type;
      if (d.entity_type === 'Vehicle') {
        subjectLabel = vehicleById.get(d.entity_id)?.plate_number ?? 'Unknown Vehicle';
      } else if (d.entity_type === 'Driver') {
        const driver = driverById.get(d.entity_id);
        subjectLabel = driver ? `${driver.first_name} ${driver.last_name}` : 'Unknown Driver';
      }
      return {
        id: d.id,
        docType: d.doc_type,
        entityType: d.entity_type,
        subjectLabel,
        expiryDate: d.expiry_date,
        daysLeft,
        urgency: urgencyOf(daysLeft),
      };
    })
    .sort((a, b) => a.daysLeft - b.daysLeft);
}

export function buildDocumentExpirySummary(entries: DocumentExpiryEntry[]): DocumentExpirySummary {
  return entries.reduce<DocumentExpirySummary>(
    (acc, e) => {
      if (e.urgency === 'expired') acc.expired += 1;
      else if (e.urgency === 'expiringSoon') acc.expiringSoon += 1;
      else acc.valid += 1;
      return acc;
    },
    { expiringSoon: 0, expired: 0, valid: 0 },
  );
}
