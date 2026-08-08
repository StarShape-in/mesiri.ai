import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { customersApi } from '../api/customersApi';
import { aggregateInvoices, aggregateRateCards, aggregateTrips } from '../services/customersService';

export const customerAggregatesKey = ['customers', 'aggregates'] as const;

/**
 * Trips, invoices and rate cards folded into per-customer lookups.
 *
 * `GET /customers` joins nothing, so these three lists are fetched once and
 * indexed by customer id — the alternative would be a request per visible row.
 * Shared by useCustomers and useCustomerStats; React Query dedupes them on
 * this key so both hooks cost one set of requests, not two.
 */
export function useCustomerAggregates() {
  const query = useQuery({
    queryKey: customerAggregatesKey,
    queryFn: async () => {
      const [trips, invoices, rateCards] = await Promise.all([
        customersApi.getTripsForAggregation(),
        customersApi.getInvoicesForAggregation(),
        customersApi.getRateCards(),
      ]);
      return { trips, invoices, rateCards };
    },
    // Derived figures move only as trips/invoices land — no need to be as fresh as the list itself.
    staleTime: 2 * 60_000,
  });

  const trips = query.data?.trips ?? [];
  const invoices = query.data?.invoices ?? [];
  const rateCards = query.data?.rateCards ?? [];

  const tripsByCustomer = useMemo(() => aggregateTrips(trips), [trips]);
  const invoicesByCustomer = useMemo(() => aggregateInvoices(invoices), [invoices]);
  const rateCardsByCustomer = useMemo(() => aggregateRateCards(rateCards), [rateCards]);

  return {
    raw: { trips, invoices, rateCards },
    tripsByCustomer,
    invoicesByCustomer,
    rateCardsByCustomer,
    loading: query.isLoading,
    error: query.isError ? 'Could not load customer activity.' : null,
    refresh: query.refetch,
  };
}
