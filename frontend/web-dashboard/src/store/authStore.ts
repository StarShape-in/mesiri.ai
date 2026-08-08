/**
 * Auth store — persists JWT token and user object in localStorage.
 * Provides simple helpers consumed across the app.
 */

import type { User } from '@mercon/shared-types';

const TOKEN_KEY  = 'mercon_token';
const USER_KEY   = 'mercon_user';

/** @deprecated alias kept for existing imports — use `User` from @mercon/shared-types */
export type AuthUser = User;

export const authStore = {
  getToken(): string | null {
    return localStorage.getItem(TOKEN_KEY);
  },

  getUser(): AuthUser | null {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
    try { return JSON.parse(raw) as AuthUser; }
    catch { return null; }
  },

  setSession(token: string, user: AuthUser) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  },

  clearSession() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },

  isAuthenticated(): boolean {
    const token = this.getToken();
    if (!token) return false;
    try {
      // Decode payload without verifying signature — server will validate on each request
      const payload = JSON.parse(atob(token.split('.')[1]));
      // exp is in seconds
      return payload.exp * 1000 > Date.now();
    } catch {
      return false;
    }
  },
};
