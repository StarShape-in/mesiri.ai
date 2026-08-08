/**
 * Customers business logic — pure transforms over API-layer data.
 * Nothing here talks to the network and nothing here invents a value.
 */
import type {
  RawCustomer,
  RawCustomerInvoice,
  RawCustomerRateCard,
  RawCustomerTrip,
} from '../api/customersApi';
import type {
  CustomerDisplayStatus,
  CustomerListItem,
  CustomerRateCard,
  CustomerSortOption,
  CustomerStats,
  CustomerStatusFilter,
} from '../types';

/** Schema default for Invoice.currency / RateCard.currency. */
export const DEFAULT_CURRENCY = 'SAR';

/** Per-customer figures folded out of the trip list. */
export interface TripAggregate {
  total: number;
  thisMonth: number;
  lastTripAt: string | null;
}

/** Per-customer figures folded out of the invoice list. */
export interface InvoiceAggregate {
  revenue: number;
  outstanding: number;
  currency: string;
}

function isSameMonth(iso: string, reference: Date): boolean {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return false;
  return d.getFullYear() === reference.getFullYear() && d.getMonth() === reference.getMonth();
}

/** Groups trips by customer into totals, this-month counts and a last-trip date. */
export function aggregateTrips(trips: RawCustomerTrip[], now = new Date()): Map<string, TripAggregate> {
  const byCustomer = new Map<string, TripAggregate>();

  for (const trip of trips) {
    if (!trip.customerId) continue;
    const current = byCustomer.get(trip.customerId) ?? { total: 0, thisMonth: 0, lastTripAt: null };

    current.total += 1;
    if (isSameMonth(trip.createdAt, now)) current.thisMonth += 1;
    if (!current.lastTripAt || new Date(trip.createdAt) > new Date(current.lastTripAt)) {
      current.lastTripAt = trip.createdAt;
    }

    byCustomer.set(trip.customerId, current);
  }

  return byCustomer;
}

/**
 * Groups invoices by customer. Revenue counts only `Paid` invoices — billed
 * but unpaid amounts are reported separately as `outstanding` so the two are
 * never conflated. `Draft` and `Cancelled` count towards neither.
 */
export function aggregateInvoices(invoices: RawCustomerInvoice[]): Map<string, InvoiceAggregate> {
  const byCustomer = new Map<string, InvoiceAggregate>();

  for (const invoice of invoices) {
    if (!invoice.customerId) continue;
    const current = byCustomer.get(invoice.customerId)
      ?? { revenue: 0, outstanding: 0, currency: invoice.currency || DEFAULT_CURRENCY };

    if (invoice.status === 'Paid') current.revenue += invoice.total_amount ?? 0;
    else if (invoice.status === 'Pending' || invoice.status === 'Overdue') {
      current.outstanding += invoice.total_amount ?? 0;
    }

    byCustomer.set(invoice.customerId, current);
  }

  return byCustomer;
}

export function toCustomerRateCard(raw: RawCustomerRateCard): CustomerRateCard {
  return {
    id: raw.id,
    name: raw.name,
    routeOrigin: raw.route_origin,
    routeDestination: raw.route_destination,
    basePrice: raw.base_price,
    currency: raw.currency || DEFAULT_CURRENCY,
    isActive: raw.is_active,
  };
}

/** Rate cards with a null customerId are the standard/default cards, not a customer's own. */
export function aggregateRateCards(rateCards: RawCustomerRateCard[]): Map<string, CustomerRateCard[]> {
  const byCustomer = new Map<string, CustomerRateCard[]>();

  for (const raw of rateCards) {
    if (!raw.customerId) continue;
    const list = byCustomer.get(raw.customerId) ?? [];
    list.push(toCustomerRateCard(raw));
    byCustomer.set(raw.customerId, list);
  }

  return byCustomer;
}

/** Only `isActive` exists in the schema, so only these two values are ever produced. */
export function customerDisplayStatus(customer: Pick<RawCustomer, 'isActive'>): CustomerDisplayStatus {
  return customer.isActive ? 'Active' : 'Inactive';
}

function countDefaultLocations(raw: RawCustomer): number {
  const hasPickup = raw.default_pickup_lat !== null && raw.default_pickup_lng !== null;
  const hasDropoff = raw.default_dropoff_lat !== null && raw.default_dropoff_lng !== null;
  return Number(hasPickup) + Number(hasDropoff);
}

export function toCustomerListItem(
  raw: RawCustomer,
  trips: Map<string, TripAggregate>,
  invoices: Map<string, InvoiceAggregate>,
  rateCards: Map<string, CustomerRateCard[]>,
): CustomerListItem {
  const tripAgg = trips.get(raw.id);
  const invoiceAgg = invoices.get(raw.id);
  const cards = rateCards.get(raw.id) ?? [];
  const activeCard = cards.find((c) => c.isActive) ?? null;

  return {
    id: raw.id,
    name: raw.name,
    phone: raw.contact_phone,
    creditLimit: raw.credit_limit ?? 0,
    isActive: raw.isActive,
    createdAt: raw.createdAt,
    status: customerDisplayStatus(raw),
    defaultLocationCount: countDefaultLocations(raw),
    rateCard: activeCard,
    rateCardCount: cards.length,
    tripsThisMonth: tripAgg?.thisMonth ?? 0,
    totalTrips: tripAgg?.total ?? 0,
    lastTripAt: tripAgg?.lastTripAt ?? null,
    revenue: invoiceAgg?.revenue ?? 0,
    outstanding: invoiceAgg?.outstanding ?? 0,
    currency: invoiceAgg?.currency ?? DEFAULT_CURRENCY,
  };
}

/**
 * Sorts client-side — `GET /customers` only ever orders by name server-side
 * (the controller hard-codes `orderBy: { name: 'asc' }`), and revenue/trips
 * are derived here anyway so the backend could not order by them.
 */
export function sortCustomers(customers: CustomerListItem[], sort: CustomerSortOption): CustomerListItem[] {
  const sorted = [...customers];
  switch (sort) {
    case 'revenue':
      return sorted.sort((a, b) => b.revenue - a.revenue);
    case 'trips':
      return sorted.sort((a, b) => b.totalTrips - a.totalTrips);
    case 'newest':
      return sorted.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
    case 'recent':
      return sorted.sort((a, b) => {
        // Customers who have never run a trip sort last rather than first.
        const aTime = a.lastTripAt ? new Date(a.lastTripAt).getTime() : -Infinity;
        const bTime = b.lastTripAt ? new Date(b.lastTripAt).getTime() : -Infinity;
        return bTime - aTime;
      });
    case 'name':
    default:
      return sorted.sort((a, b) => a.name.localeCompare(b.name));
  }
}

export function statusFilterToIsActive(status: CustomerStatusFilter): boolean | undefined {
  if (status === 'active') return true;
  if (status === 'inactive') return false;
  return undefined;
}

/**
 * Screen-level KPIs.
 *
 * `totalCustomers` comes from the list endpoint's `meta.total` (the true
 * server-side count) rather than the number of rows loaded so far, which
 * would climb as the user scrolls.
 */
export function computeCustomerStats(
  totalCustomers: number,
  trips: RawCustomerTrip[],
  invoices: RawCustomerInvoice[],
  rateCards: RawCustomerRateCard[],
  now = new Date(),
): CustomerStats {
  return {
    totalCustomers,
    activeRateCards: rateCards.filter((c) => c.is_active).length,
    tripsThisMonth: trips.filter((t) => isSameMonth(t.createdAt, now)).length,
    pendingBills: invoices.filter((i) => i.status === 'Pending' || i.status === 'Overdue').length,
  };
}

export function customerInitials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return '?';
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return `${words[0][0]}${words[1][0]}`.toUpperCase();
}

/** "SAR 12,400" — whole units; fractional riyals add noise at list density. */
export function formatMoney(amount: number, currency = DEFAULT_CURRENCY): string {
  return `${currency} ${Math.round(amount || 0).toLocaleString()}`;
}

/** "12.4K" style compaction for the tight revenue column on narrow phones. */
export function formatCompactMoney(amount: number, currency = DEFAULT_CURRENCY): string {
  const value = Math.round(amount || 0);
  if (value >= 1_000_000) return `${currency} ${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 10_000) return `${currency} ${(value / 1000).toFixed(1)}K`;
  return `${currency} ${value.toLocaleString()}`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleDateString(undefined, { month: 'short', year: 'numeric' });
}
