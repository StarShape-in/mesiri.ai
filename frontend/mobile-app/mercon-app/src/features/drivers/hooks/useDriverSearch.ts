import { useState } from 'react';
import { useDebouncedValue } from '@/shared/hooks';

/** Debounced search input — `query` updates immediately for the text field, `debouncedQuery` is what should trigger a refetch. */
export function useDriverSearch(delayMs = 350) {
  const [query, setQuery] = useState('');
  const debouncedQuery = useDebouncedValue(query, delayMs);

  return { query, debouncedQuery, setQuery };
}
