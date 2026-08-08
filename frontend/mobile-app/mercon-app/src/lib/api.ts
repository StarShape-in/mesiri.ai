/**
 * API client for the MERCON backend.
 * Base URL comes from EXPO_PUBLIC_API_URL (set in .env or eas.json),
 * falling back to the production server.
 */
import axios from 'axios';
import { safeSecureStore as SecureStore } from './secure-store';
import { router } from 'expo-router';

export const API_URL = process.env.EXPO_PUBLIC_API_URL ?? 'https://mercon.tech/api';

export const TOKEN_KEY = 'mercon_token';
export const SESSION_KEY = 'mercon_session';

const LOGIN_PATHS = ['/auth/login', '/mobile/auth/login'];

export const api = axios.create({
  baseURL: API_URL,
  timeout: 15000,
});

// Attach the saved JWT to every request
api.interceptors.request.use(async (config) => {
  const token = await SecureStore.getItemAsync(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// A 401 on any authenticated request means the token expired or was revoked.
// Previously every screen just showed a generic "Something went wrong" alert
// with no path back to login — the driver had to manually find Settings →
// Logout. Now the session is cleared and the app returns to login directly.
// Login attempts themselves are excluded: a 401 there is just "wrong
// credentials" (handled by auth-context's dual-endpoint signIn), not an
// expired session, and there's no session to clear yet anyway.
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const isLoginRequest = LOGIN_PATHS.some((p) => error.config?.url?.includes(p));
    if (error.response?.status === 401 && !isLoginRequest) {
      await Promise.all([
        SecureStore.deleteItemAsync(TOKEN_KEY),
        SecureStore.deleteItemAsync(SESSION_KEY),
      ]);
      router.replace('/login');
    }
    return Promise.reject(error);
  },
);

/**
 * Standard error envelope from the backend: { success: false, error: { code, message } }.
 * Always logs the raw error first — this used to fall through to a generic
 * "Something went wrong" with no trace of what actually failed (network vs.
 * server vs. a plain JS exception from something like FormData/file reading),
 * which made real bugs indistinguishable from transient hiccups. Now the
 * console log (visible in Metro) and the alert text itself carry the real
 * cause so the next occurrence is diagnosable on the spot.
 */
export function getApiErrorMessage(err: unknown): string {
  console.error('[API error]', err);

  if (axios.isAxiosError(err)) {
    if (err.response?.data?.error?.message) return err.response.data.error.message;
    if (err.code === 'ECONNABORTED') return 'Request timed out. Check your connection.';
    if (!err.response) {
      return `Cannot reach the server (${err.message || err.code || 'network error'}). Check your connection.`;
    }
    return `Server error (HTTP ${err.response.status}). Please try again.`;
  }

  if (err instanceof Error) {
    return `Something went wrong: ${err.message}`;
  }
  return 'Something went wrong. Please try again.';
}
