import { useState } from 'react';
import { useDebouncedValue } from '@/shared/hooks';

/**
 * Search box state. The debounced value is what reaches the query key, so
 * typing does not fire a request per keystroke — `GET /customers` searches
 * server-side by name.
 */
export function useCustomerSearch(delay = 300) {
  const [query, setQuery] = useState('');
  const debouncedQuery = useDebouncedValue(query, delay);

  return {
    query,
    setQuery,
    debouncedQuery,
    clear: () => setQuery(''),
    isSearching: query.trim().length > 0,
  };
}
