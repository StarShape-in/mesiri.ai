import { useCallback, useEffect, useState } from 'react';
import { profileService, type DriverProfile } from './profile';
import { getApiErrorMessage } from './api';

/** Loads the driver's profile. Fetch-on-mount with a manual refetch. */
export function useProfile() {
  const [profile, setProfile] = useState<DriverProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setProfile(await profileService.get());
    } catch (e) {
      setError(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refetch(); }, [refetch]);

  return { profile, loading, error, refetch };
}
