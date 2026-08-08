/**
 * Driver profile — GET /mobile/profile.
 * Assigned vehicle comes from the driver's current active trip (drivers have
 * no standing vehicle assignment), so it's null when there's no active trip.
 */
import { api } from './api';

export interface DriverProfile {
  id: string;
  ref_id: string | null;
  name: string;
  first_name: string;
  last_name: string;
  phone_primary: string | null;
  status: string;
  license_number: string;
  license_expiry: string;
  createdAt: string;
  current_vehicle: { id: string; plate_number: string; asset_type: string } | null;
}

export const profileService = {
  async get(): Promise<DriverProfile> {
    const { data } = await api.get('/mobile/profile');
    return data.data as DriverProfile;
  },
};

/** Up to two initials from a name, for the avatar. */
export function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}
