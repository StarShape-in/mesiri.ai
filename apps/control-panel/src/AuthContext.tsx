import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { fetchMe, getToken, type Me } from './api';

interface AuthState {
  me: Me | null;
  loading: boolean;
}

const AuthContext = createContext<AuthState>({ me: null, loading: true });

export const useAuth = () => useContext(AuthContext);

/**
 * Wraps protected routes. A token existing in localStorage is never treated
 * as a valid session on its own — this always confirms it against the
 * server via GET /auth/me before rendering children. If that call fails,
 * api.ts's response interceptor has already cleared the token and will
 * redirect; this component just avoids rendering protected content in the
 * meantime.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ me: null, loading: true });

  useEffect(() => {
    if (!getToken()) {
      setState({ me: null, loading: false });
      return;
    }
    fetchMe()
      .then((me) => setState({ me, loading: false }))
      .catch(() => setState({ me: null, loading: false }));
  }, []);

  if (state.loading) {
    return <div className="animate-fade-in" style={{ padding: 'var(--space-8)' }}>Checking session…</div>;
  }

  if (!state.me) {
    return <Navigate to="/login" replace />;
  }

  return <AuthContext.Provider value={state}>{children}</AuthContext.Provider>;
}
