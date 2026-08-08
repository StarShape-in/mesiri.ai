import { useCallback } from 'react';
import { Alert, Linking } from 'react-native';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { driverDetailsApi, type RawDriverDetail } from '../api/driverDetailsApi';
import { getApiErrorMessage } from '@/lib/api';
import { driverDetailKey } from './useDriver';
import type { DriverStatus } from '../types';

export interface UseDriverActionsResult {
  /** Opens the dialer. No-ops with an alert when the driver has no phone number on record. */
  callDriver: () => Promise<void>;
  /** Opens the SMS composer. Same no-phone handling as callDriver. */
  messageDriver: () => Promise<void>;
  /** PATCHes the driver's duty status, applied optimistically and rolled back on failure. */
  setStatus: (status: DriverStatus) => void;
  isUpdatingStatus: boolean;
  canContact: boolean;
}

async function openUrl(url: string, unavailableMessage: string): Promise<void> {
  try {
    const supported = await Linking.canOpenURL(url);
    if (!supported) {
      Alert.alert('Not available', unavailableMessage);
      return;
    }
    await Linking.openURL(url);
  } catch (err) {
    Alert.alert('Could not open', getApiErrorMessage(err));
  }
}

/**
 * Side-effecting actions for one driver. Kept out of the presentation layer so
 * the cards and buttons stay dumb.
 *
 * @param phone The driver's `phone_primary`; null disables the contact actions
 *              rather than dialling an empty number.
 */
export function useDriverActions(driverId: string | undefined, phone: string | null): UseDriverActionsResult {
  const queryClient = useQueryClient();
  const canContact = !!phone;

  const callDriver = useCallback(async () => {
    if (!phone) {
      Alert.alert('No phone number', 'This driver has no phone number on record.');
      return;
    }
    await openUrl(`tel:${phone}`, 'This device cannot place calls.');
  }, [phone]);

  const messageDriver = useCallback(async () => {
    if (!phone) {
      Alert.alert('No phone number', 'This driver has no phone number on record.');
      return;
    }
    await openUrl(`sms:${phone}`, 'This device cannot send messages.');
  }, [phone]);

  const statusMutation = useMutation({
    mutationFn: (status: DriverStatus) => driverDetailsApi.updateDriverStatus(driverId as string, status),

    // Optimistic: paint the new status immediately, keeping the previous
    // record so a failed PATCH can put it back exactly as it was.
    onMutate: async (status) => {
      if (!driverId) return { previous: undefined };
      const key = driverDetailKey(driverId);
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<RawDriverDetail>(key);
      if (previous) {
        queryClient.setQueryData<RawDriverDetail>(key, { ...previous, status });
      }
      return { previous };
    },

    onError: (err, _status, context) => {
      if (driverId && context?.previous) {
        queryClient.setQueryData(driverDetailKey(driverId), context.previous);
      }
      Alert.alert('Update failed', getApiErrorMessage(err));
    },

    // Re-sync with the server either way: the list and the detail both show status.
    onSettled: () => {
      if (driverId) queryClient.invalidateQueries({ queryKey: driverDetailKey(driverId) });
      queryClient.invalidateQueries({ queryKey: ['drivers', 'list'] });
    },
  });

  const setStatus = useCallback(
    (status: DriverStatus) => {
      if (!driverId) return;
      statusMutation.mutate(status);
    },
    [driverId, statusMutation],
  );

  return {
    callDriver,
    messageDriver,
    setStatus,
    isUpdatingStatus: statusMutation.isPending,
    canContact,
  };
}
