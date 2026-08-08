/**
 * Domain types for the Customers feature.
 * Mirrors the backend's Customer/Trip/Invoice/RateCard Prisma models — see
 * backend/api-server/prisma/schema.prisma for the source of truth.
 *
 * The Customer model is deliberately small (name, contact_phone, credit_limit,
 * default pickup/dropoff coordinates, isActive). Everything richer on this
 * screen — trips, revenue, rate cards — is *derived* from the customer's real
 * trips/invoices/rate cards, never invented.
 */

/** Mirrors the backend's `InvoiceStatus` enum. */
export type InvoiceStatus = 'Draft' | 'Pending' | 'Paid' | 'Overdue' | 'Cancelled';

/**
 * Display vocabulary for CustomerStatusBadge.
 *
 * The backend tracks a single `isActive` boolean, so only `Active` and
 * `Inactive` are ever produced from real data. `OnHold` / `ContractExpired` /
 * `Cancelled` have no backing column — the badge accepts them so it is ready
 * if a status field is added, but nothing in this feature emits them
 * (CLAUDE.md Rule 0: no invented enum values).
 */
export type CustomerDisplayStatus =
  | 'Active'
  | 'Inactive'
  | 'OnHold'
  | 'ContractExpired'
  | 'Cancelled';

export interface CustomerRateCard {
  id: string;
  name: string;
  routeOrigin: string;
  routeDestination: string;
  basePrice: number;
  currency: string;
  isActive: boolean;
}

export interface CustomerListItem {
  id: string;
  name: string;
  phone: string;
  creditLimit: number;
  isActive: boolean;
  createdAt: string;
  status: CustomerDisplayStatus;

  /**
   * How many of the customer's two optional default coordinates are set
   * (0–2). There is no Location entity — this is the honest reading of
   * "locations" against the real schema.
   */
  defaultLocationCount: number;

  /** The customer's active rate card, or null when they are on standard rates. */
  rateCard: CustomerRateCard | null;
  rateCardCount: number;

  tripsThisMonth: number;
  totalTrips: number;
  /** ISO date of the customer's most recent trip, or null. Drives "Recently Active" sorting. */
  lastTripAt: string | null;

  /** Sum of this customer's `Paid` invoices. */
  revenue: number;
  /** Sum of this customer's `Pending` + `Overdue` invoices. */
  outstanding: number;
  /** Currency from the customer's invoices; falls back to the schema default. */
  currency: string;
}

export interface CustomerListPage {
  customers: CustomerListItem[];
  meta: { page: number; per_page: number; total: number; total_pages: number };
}

export interface CustomerStats {
  totalCustomers: number;
  /**
   * Rate cards are the only commercial agreement the schema models — there is
   * no Contract entity, so this counts active rate cards rather than
   * pretending contracts exist.
   */
  activeRateCards: number;
  tripsThisMonth: number;
  /** Invoices in `Pending` or `Overdue`. */
  pendingBills: number;
}

/**
 * "Contract Expiry" is intentionally absent: rate cards carry no validity
 * dates, so there is nothing real to sort by.
 */
export type CustomerSortOption = 'name' | 'revenue' | 'trips' | 'newest' | 'recent';

export type CustomerStatusFilter = 'all' | 'active' | 'inactive';

export interface CustomerListParams {
  search?: string;
  status?: CustomerStatusFilter;
  page?: number;
  per_page?: number;
}

/** Derived from the authenticated user's role — see useCustomerPermissions. */
export interface CustomerPermissions {
  canCreate: boolean;
  canEdit: boolean;
  canSuspend: boolean;
  canDelete: boolean;
}
