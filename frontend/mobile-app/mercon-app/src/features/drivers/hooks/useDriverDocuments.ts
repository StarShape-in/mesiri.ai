import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { driverDetailsApi } from '../api/driverDetailsApi';
import { sortDocumentsByUrgency, toDriverDocument } from '../services/driverDetailsService';
import type { DriverDocument } from '../types';

export function driverDocumentsKey(driverId: string) {
  return ['drivers', 'detail', driverId, 'documents'] as const;
}

export interface UseDriverDocumentsResult {
  documents: DriverDocument[];
  /** Documents already expired or inside the 30-day window — drives the section's "N need attention" hint. */
  needsAttention: number;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

/**
 * The driver's compliance documents, most-urgent first.
 *
 * Read from GET /documents (filtered to this driver) rather than the
 * `documents` array GET /drivers/:id embeds, so the section can refetch on its
 * own after an upload without pulling the whole driver record down again.
 */
export function useDriverDocuments(driverId: string | undefined): UseDriverDocumentsResult {
  const query = useQuery({
    queryKey: driverDocumentsKey(driverId ?? ''),
    queryFn: () => driverDetailsApi.getDriverDocuments(driverId as string),
    enabled: !!driverId,
    // Documents change as they are renewed/verified — keep fresher than the 30s default.
    staleTime: 60_000,
  });

  const documents = useMemo(
    () => sortDocumentsByUrgency((query.data ?? []).map(toDriverDocument)),
    [query.data],
  );

  const needsAttention = useMemo(
    () => documents.filter((d) => d.displayStatus === 'Expired' || d.displayStatus === 'ExpiresSoon').length,
    [documents],
  );

  return {
    documents,
    needsAttention,
    loading: query.isLoading,
    error: query.isError ? 'Could not load documents.' : null,
    refresh: query.refetch,
  };
}
