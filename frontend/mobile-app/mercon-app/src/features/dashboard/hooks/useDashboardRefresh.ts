/** Pull-to-refresh: invalidates every query under the ['dashboard', ...] namespace. */
import { useCallback, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';

export function useDashboardRefresh() {
  const queryClient = useQueryClient();
  const [refreshing, setRefreshing] = useState(false);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    } finally {
      setRefreshing(false);
    }
  }, [queryClient]);

  return { refreshing, refresh };
}
