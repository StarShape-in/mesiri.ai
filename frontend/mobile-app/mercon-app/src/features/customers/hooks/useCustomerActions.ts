import { useCallback } from 'react';
import { Alert } from 'react-native';
import { useMutation, useQueryClient, type InfiniteData } from '@tanstack/react-query';
import { customersApi, type RawCustomerListResponse } from '../api/customersApi';
import { getApiErrorMessage } from '@/lib/api';
import type { CustomerListItem } from '../types';

type CustomersInfiniteData = InfiniteData<RawCustomerListResponse, number>;

/** Every cached customer list page, regardless of its search/filter key. */
const LIST_PREFIX = ['customers', 'list'] as const;

export interface UseCustomerActionsResult {
  /** Flips `isActive`, applied optimistically across every cached list page. */
  toggleActive: (customer: CustomerListItem) => void;
  /** Soft-deletes after a confirmation prompt. */
  deleteCustomer: (customer: CustomerListItem) => void;
  isMutating: boolean;
}

/**
 * Side-effecting customer actions. Kept out of the presentation layer so the
 * card and its overflow menu stay dumb.
 *
 * Callers are responsible for permission checks (useCustomerPermissions) —
 * these functions do not re-check, they just act.
 */
export function useCustomerActions(): UseCustomerActionsResult {
  const queryClient = useQueryClient();

  const invalidate = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: LIST_PREFIX });
    queryClient.invalidateQueries({ queryKey: ['customers', 'aggregates'] });
    queryClient.invalidateQueries({ queryKey: ['customers', 'total-count'] });
  }, [queryClient]);

  const activeMutation = useMutation({
    mutationFn: ({ id, isActive }: { id: string; isActive: boolean }) =>
      customersApi.setCustomerActive(id, isActive),

    // Optimistic: patch the row in every cached page so the badge flips at
    // once, keeping the snapshots to restore exactly on failure.
    onMutate: async ({ id, isActive }) => {
      await queryClient.cancelQueries({ queryKey: LIST_PREFIX });
      const snapshots = queryClient.getQueriesData<CustomersInfiniteData>({ queryKey: LIST_PREFIX });

      for (const [key, data] of snapshots) {
        if (!data) continue;
        queryClient.setQueryData<CustomersInfiniteData>(key, {
          ...data,
          pages: data.pages.map((page) => ({
            ...page,
            data: page.data.map((c) => (c.id === id ? { ...c, isActive } : c)),
          })),
        });
      }

      return { snapshots };
    },

    onError: (err, _vars, context) => {
      for (const [key, data] of context?.snapshots ?? []) {
        queryClient.setQueryData(key, data);
      }
      Alert.alert('Update failed', getApiErrorMessage(err));
    },

    onSettled: invalidate,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => customersApi.deleteCustomer(id),

    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: LIST_PREFIX });
      const snapshots = queryClient.getQueriesData<CustomersInfiniteData>({ queryKey: LIST_PREFIX });

      for (const [key, data] of snapshots) {
        if (!data) continue;
        queryClient.setQueryData<CustomersInfiniteData>(key, {
          ...data,
          pages: data.pages.map((page) => ({
            ...page,
            data: page.data.filter((c) => c.id !== id),
          })),
        });
      }

      return { snapshots };
    },

    onError: (err, _id, context) => {
      for (const [key, data] of context?.snapshots ?? []) {
        queryClient.setQueryData(key, data);
      }
      Alert.alert('Delete failed', getApiErrorMessage(err));
    },

    onSettled: invalidate,
  });

  const toggleActive = useCallback(
    (customer: CustomerListItem) => {
      const suspending = customer.isActive;
      Alert.alert(
        suspending ? 'Suspend customer' : 'Reactivate customer',
        suspending
          ? `${customer.name} will be marked inactive. Existing trips and invoices are not affected.`
          : `${customer.name} will be marked active again.`,
        [
          { text: 'Cancel', style: 'cancel' },
          {
            text: suspending ? 'Suspend' : 'Reactivate',
            style: suspending ? 'destructive' : 'default',
            onPress: () => activeMutation.mutate({ id: customer.id, isActive: !customer.isActive }),
          },
        ],
      );
    },
    [activeMutation],
  );

  const deleteCustomer = useCallback(
    (customer: CustomerListItem) => {
      Alert.alert(
        'Delete customer',
        `Delete ${customer.name}? Their trips and invoices remain, but the customer is removed from lists.`,
        [
          { text: 'Cancel', style: 'cancel' },
          { text: 'Delete', style: 'destructive', onPress: () => deleteMutation.mutate(customer.id) },
        ],
      );
    },
    [deleteMutation],
  );

  return {
    toggleActive,
    deleteCustomer,
    isMutating: activeMutation.isPending || deleteMutation.isPending,
  };
}
