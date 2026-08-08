import { useQuery } from '@tanstack/react-query';
import { dashboardApi } from '../api/dashboardApi';
import { buildDocumentExpiryEntries, buildDocumentExpirySummary } from '../services/dashboardService';
import type { DocumentFilterScope } from '../types';

export function documentExpiryKey(scope: DocumentFilterScope) {
  return ['dashboard', 'document-expiry', scope] as const;
}

/** Documents with a real expiry date, joined with their vehicle/driver, scoped to the filter tab — with a summary + refresh for the Document Expiry section. */
export function useDocumentExpiry(scope: DocumentFilterScope) {
  const query = useQuery({
    queryKey: documentExpiryKey(scope),
    queryFn: async () => {
      const [documents, vehicles, drivers] = await Promise.all([
        dashboardApi.getDocuments(),
        dashboardApi.getVehicles(),
        dashboardApi.getDrivers(),
      ]);
      const documentsList = buildDocumentExpiryEntries(documents, vehicles, drivers, scope);
      return { documents: documentsList, summary: buildDocumentExpirySummary(documentsList) };
    },
    // The list changes as documents get renewed/expire — keep it fresher than the default.
    staleTime: 60_000,
    refetchInterval: 5 * 60_000,
  });

  return {
    summary: query.data?.summary,
    documents: query.data?.documents ?? [],
    loading: query.isLoading,
    error: query.isError ? 'Could not load document expiry data.' : null,
    refresh: query.refetch,
  };
}
