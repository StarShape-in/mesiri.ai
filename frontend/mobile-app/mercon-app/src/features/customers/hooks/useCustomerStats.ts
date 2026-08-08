import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { customersApi } from '../api/customersApi';
import { computeCustomerStats } from '../services/customersService';
import { useCustomerAggregates } from './useCustomerAggregates';
import type { CustomerStats } from '../types';

export const customerCountKey = ['customers', 'total-count'] as const;

const EMPTY: CustomerStats = {
  totalCustomers: 0,
  activeRateCards: 0,
  tripsThisMonth: 0,
  pendingBills: 0,
};

/**
 * Screen KPIs.
 *
 * The customer count is read from `meta.total` of a single-row request rather
 * than counting loaded rows, so it stays correct regardless of how far the
 * user has scrolled. The rest is folded from the shared aggregates.
 */
export function useCustomerStats(): {
  stats: CustomerStats;
  loading: boolean;
  error: string | null;
  refresh: () => void;
} {
  const aggregates = useCustomerAggregates();

  const countQuery = useQuery({
    queryKey: customerCountKey,
    queryFn: () => customersApi.getCustomers({ page: 1, per_page: 1 }),
    staleTime: 2 * 60_000,
  });

  const stats = useMemo(() => {
    const total = countQuery.data?.meta.total;
    if (total === undefined) return EMPTY;
    return computeCustomerStats(
      total,
      aggregates.raw.trips,
      aggregates.raw.invoices,
      aggregates.raw.rateCards,
    );
  }, [countQuery.data, aggregates.raw]);

  return {
    stats,
    loading: countQuery.isLoading || aggregates.loading,
    error: countQuery.isError ? 'Could not load customer statistics.' : aggregates.error,
    refresh: () => {
      countQuery.refetch();
      aggregates.refresh();
    },
  };
}
