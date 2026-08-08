import { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { authStore } from '@/store/authStore';

interface RequireRoleProps {
  roles: string[];
  children: ReactNode;
}

export default function RequireRole({ roles, children }: RequireRoleProps) {
  const user = authStore.getUser();

  if (!user || !roles.includes(user.role)) {
    // Redirect to dashboard if they don't have permission
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}
