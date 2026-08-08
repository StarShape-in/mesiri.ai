import { z } from 'zod';

/* ─── Shared building blocks ─────────────────────────────────────────────── */

/** A required, trimmed, non-empty string. */
const nonEmpty = (label = 'Value') => z.string().trim().min(1, `${label} is required`);

/** Route param `:id` must be a UUID. */
export const idParam = z.object({ id: z.string().uuid('Invalid id') });

/** List query — pagination + search + sort. Coerces and guards against NaN. */
export const listQuery = z.object({
  page: z.coerce.number().int().positive().default(1),
  per_page: z.coerce.number().int().positive().max(200).default(20),
  search: z.string().trim().optional(),
  sort_by: z.string().trim().optional(),
  sort_dir: z.enum(['asc', 'desc']).default('desc'),
  status: z.string().trim().optional(),
  customer_id: z.string().uuid().optional(),
}).passthrough();

/* ─── Auth ───────────────────────────────────────────────────────────────── */
export const loginBody = z.object({
  username: nonEmpty('Username'),
  password: nonEmpty('Password'),
});

/* ─── Trips ──────────────────────────────────────────────────────────────── */
export const createTripBody = z.object({
  customer_id: z.string().uuid('A valid customer is required'),
  driver_id: z.string().uuid('Invalid driver').optional(),
  vehicle_id: z.string().uuid('Invalid vehicle').optional(),
  cargo_type: z.string().trim().optional().default('General Goods'),
  planned_start: z.coerce.date().optional(),
  stops: z.array(z.object({
    stop_type: z.enum(['Pickup', 'Dropoff', 'Rest', 'Refuel']),
    // Client + controller use lat/lng (controller reads stop.lat/stop.lng), not location_*.
    lat: z.coerce.number(),
    lng: z.coerce.number(),
    planned_arrival: z.string().optional(),
    // Human-readable name for this place — the route label in delay reports.
    location_name: z.string().trim().max(120).optional(),
    stop_sequence: z.number().int().optional(),
  })).min(2, 'At least a pickup and a dropoff are required'),
});

/** Operator logging why a stop was reached late. Reason is required — the
 *  whole point is replacing "no explanation" with one, and `Other` plus a note
 *  already covers anything the list misses. */
export const logStopDelayBody = z.object({
  delay_reason: z.enum([
    'Traffic', 'VehicleBreakdown', 'CustomerNotReady', 'SlowLoadingUnloading',
    'Weather', 'Documentation', 'RouteBlocked', 'Other',
  ]),
  delay_note: z.string().trim().max(500).optional(),
});

/* ─── Drivers ────────────────────────────────────────────────────────────── */
export const createDriverBody = z.object({
  first_name: nonEmpty('First name'),
  last_name: nonEmpty('Last name'),
  phone_primary: nonEmpty('Phone number'),
  license_number: nonEmpty('License number'),
  license_expiry: z.coerce.date(),
});

// Partial update: every field optional, unknown keys stripped, and
// license_expiry coerced to a real Date (Prisma rejects bare date strings).
export const updateDriverBody = z.object({
  first_name: nonEmpty('First name').optional(),
  last_name: nonEmpty('Last name').optional(),
  phone_primary: nonEmpty('Phone number').optional(),
  license_number: nonEmpty('License number').optional(),
  license_expiry: z.coerce.date().optional(),
  status: z.enum(['Available', 'OnTrip', 'OffDuty', 'Inactive']).optional(),
});

/* ─── Customers ──────────────────────────────────────────────────────────── */
export const createCustomerBody = z.object({
  name: nonEmpty('Customer name'),
  contact_phone: nonEmpty('Contact phone'),
  credit_limit: z.coerce.number().nonnegative().optional(),
});

export const updateCustomerBody = z.object({
  name: nonEmpty('Customer name').optional(),
  contact_phone: nonEmpty('Contact phone').optional(),
  credit_limit: z.coerce.number().nonnegative().optional(),
  isActive: z.boolean().optional(),
});

/* ─── Vehicles ───────────────────────────────────────────────────────────── */
export const createVehicleBody = z.object({
  plate_number: nonEmpty('Plate number'),
  asset_type: z.enum(['Flatbed', 'Reefer', 'Box', 'Tanker']),
  capacity_kg: z.coerce.number().int().positive('Capacity must be a whole number of kg'),
  trailer_number: z.string().trim().optional(),
  trailer_type: z.enum(['Flatbed', 'Reefer', 'Box', 'Tanker']).optional(),
  trailer_capacity_kg: z.coerce.number().int().positive().optional(),
  gps_device_id: z.string().trim().optional(),
  icces_device_id: z.string().trim().optional(),
});

export const updateVehicleBody = z.object({
  plate_number: nonEmpty('Plate number').optional(),
  asset_type: z.enum(['Flatbed', 'Reefer', 'Box', 'Tanker']).optional(),
  capacity_kg: z.coerce.number().int().positive().optional(),
  trailer_number: z.string().trim().optional(),
  trailer_type: z.enum(['Flatbed', 'Reefer', 'Box', 'Tanker']).optional(),
  trailer_capacity_kg: z.coerce.number().int().positive().optional(),
  gps_device_id: z.string().trim().optional(),
  icces_device_id: z.string().trim().optional(),
  status: z.enum(['Available', 'OnTrip', 'Maintenance', 'Inactive']).optional(),
});

/* ─── Users (Admin-only web dashboard accounts) ─────────────────────────────
 * Only Admin/Operator are creatable here — Driver accounts are managed
 * through the Drivers module, never through User Management. See
 * CLAUDE.md "Roles" and "Who uses which app".
 */
const webUserRole = z.enum(['Admin', 'Operator']);

export const createUserBody = z.object({
  name: nonEmpty('Name'),
  email: z.string().trim().email('A valid email is required'),
  role: webUserRole,
  password: nonEmpty('Password'),
});

export const updateUserBody = z.object({
  name: nonEmpty('Name').optional(),
  email: z.string().trim().email('A valid email is required').optional(),
  role: webUserRole.optional(),
  status: z.enum(['Active', 'Inactive']).optional(),
  password: nonEmpty('Password').optional(),
});

/* ─── Invoices ───────────────────────────────────────────────────────────── */
export const createInvoiceBody = z.object({
  trip_id: z.string().uuid('A valid trip is required'),
  customer_id: z.string().uuid('A valid customer is required'),
  subtotal: z.coerce.number().nonnegative(),
  total_amount: z.coerce.number().nonnegative(),
  due_date: z.coerce.date(),
});
