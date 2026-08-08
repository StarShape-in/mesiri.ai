import { useMemo } from 'react';
import { useAuth } from '@/lib/auth-context';
import type { CustomerPermissions } from '../types';

/**
 * Customer permissions derived from the authenticated user's real role
 * (persisted from the backend's login response).
 *
 * The backend gates every /customers route with
 * `authorizeRoles('Admin', 'Operator')`, so create/edit/suspend mirror that
 * exactly. Delete is additionally narrowed to Admin here — a deliberate UI
 * guard, since a soft delete of a customer with trip and invoice history is
 * not something a Dispatcher should reach by accident.
 *
 * NOTE: that narrowing is UI-only. The backend still accepts DELETE from an
 * Operator, so it is not a security boundary — see CLAUDE.md ("Frontend-only
 * gating is not security"). Enforcing it properly means changing
 * `customerRoutes.ts` to `authorizeRoles('Admin')` on the delete route.
 */
export function useCustomerPermissions(): CustomerPermissions {
  const { role } = useAuth();

  return useMemo(() => {
    const isAdmin = role === 'Admin';
    const canManage = isAdmin || role === 'Operator';

    return {
      canCreate: canManage,
      canEdit: canManage,
      canSuspend: canManage,
      canDelete: isAdmin,
    };
  }, [role]);
}
