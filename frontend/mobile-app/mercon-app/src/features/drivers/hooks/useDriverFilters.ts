import { useState } from 'react';
import type { DriverStatus } from '../types';

/** Selected status filter for the driver list — null means "All". */
export function useDriverFilters() {
  const [status, setStatus] = useState<DriverStatus | null>(null);
  return { status, setStatus };
}
