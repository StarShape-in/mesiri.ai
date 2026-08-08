import { useState } from 'react';
import type { DriverSortOption } from '../types';

export function useDriverSorting(initial: DriverSortOption = 'name') {
  const [sort, setSort] = useState<DriverSortOption>(initial);
  return { sort, setSort };
}
