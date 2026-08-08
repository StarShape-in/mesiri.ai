/**
 * Customers API layer — raw HTTP only, no business logic and no shape
 * transformation beyond unwrapping the `{ success, data, meta }` envelope.
 *
 * Endpoints (all already exist; nothing here needs a backend change):
 *   GET    /customers          → paginated, name-searchable, is_active filter
 *   PATCH  /customers/:id      → rename / re-phone / credit limit / isActive
 *   DELETE /customers/:id      → soft delete
 *   GET    /trips              → aggregated client-side into per-customer counts
 *   GET    /invoices           → aggregated client-side into revenue / outstanding
 *   GET    /rate-cards         → the customer's commercial rate card
 *
 * `GET /customers` returns scalar customer columns only — it joins nothing —
 * so trips/revenue/rate-cards are fetched once each and aggregated by
 * customer id rather than issuing a request per row (which would be N+1).
 */
import { api } from '@/lib/api';
import type { InvoiceStatus } from '../types';

export interface RawCustomer {
  id: string;
  name: string;
  contact_phone: string;
  credit_limit: number;
  default_pickup_lat: number | null;
  default_pickup_lng: number | null;
  default_dropoff_lat: number | null;
  default_dropoff_lng: number | null;
  isActive: boolean;
  createdAt: string;
}

export interface RawCustomerListResponse {
  data: RawCustomer[];
  meta: { page: number; per_page: number; total: number; total_pages: number };
}

/** Only the fields the aggregation needs. */
export interface RawCustomerTrip {
  id: string;
  customerId: string;
  status: string;
  createdAt: string;
}

export interface RawCustomerInvoice {
  id: string;
  customerId: string;
  status: InvoiceStatus;
  total_amount: number;
  currency: string;
}

export interface RawCustomerRateCard {
  id: string;
  name: string;
  route_origin: string;
  route_destination: string;
  base_price: number;
  currency: string;
  customerId: string | null;
  is_active: boolean;
}

/** Aggregation reads are capped rather than paged: the figures are all-time totals. */
const AGGREGATE_PAGE_SIZE = 500;

export const customersApi = {
  async getCustomers(params: {
    page?: number;
    per_page?: number;
    search?: string;
    is_active?: boolean;
  }): Promise<RawCustomerListResponse> {
    const { data } = await api.get('/customers', {
      params: {
        page: params.page ?? 1,
        per_page: params.per_page ?? 20,
        search: params.search || undefined,
        is_active: params.is_active === undefined ? undefined : String(params.is_active),
      },
    });
    return { data: data.data ?? [], meta: data.meta };
  },

  async getTripsForAggregation(): Promise<RawCustomerTrip[]> {
    const { data } = await api.get('/trips', { params: { per_page: AGGREGATE_PAGE_SIZE } });
    return (data.data ?? []) as RawCustomerTrip[];
  },

  async getInvoicesForAggregation(): Promise<RawCustomerInvoice[]> {
    const { data } = await api.get('/invoices', { params: { per_page: AGGREGATE_PAGE_SIZE } });
    return (data.data ?? []) as RawCustomerInvoice[];
  },

  /** GET /rate-cards is unpaginated by design in the controller. */
  async getRateCards(): Promise<RawCustomerRateCard[]> {
    const { data } = await api.get('/rate-cards');
    return (data.data ?? []) as RawCustomerRateCard[];
  },

  async setCustomerActive(customerId: string, isActive: boolean): Promise<RawCustomer> {
    const { data } = await api.patch(`/customers/${customerId}`, { isActive });
    return data.data as RawCustomer;
  },

  async deleteCustomer(customerId: string): Promise<void> {
    await api.delete(`/customers/${customerId}`);
  },
};
