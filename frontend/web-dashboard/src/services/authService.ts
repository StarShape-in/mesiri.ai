import { api, ApiResponse } from '@/lib/api';
import { authStore, AuthUser } from '@/store/authStore';

export interface LoginPayload {
  username: string;
  password: string;
}
export interface LoginResult {
  token: string;
  expires_at: string;
  user: AuthUser;
}

export const authService = {
  async login(payload: LoginPayload): Promise<LoginResult> {
    const res = await api.post<ApiResponse<LoginResult>>('/auth/login', payload);
    const { token, user } = res.data.data;
    authStore.setSession(token, user);
    return res.data.data;
  },

  async getMe(): Promise<AuthUser> {
    const res = await api.get<ApiResponse<AuthUser>>('/auth/me');
    return res.data.data;
  },

  async updateMe(payload: { name?: string; email?: string; phone?: string }): Promise<AuthUser> {
    const res = await api.patch<ApiResponse<AuthUser>>('/auth/me', payload);
    const current = authStore.getUser();
    if (current) authStore.setSession(authStore.getToken()!, { ...current, ...res.data.data });
    return res.data.data;
  },

  async changePassword(current_password: string, new_password: string): Promise<void> {
    await api.post('/auth/change-password', { current_password, new_password });
  },

  /** Notify all operators/admins that this user needs a password reset. */
  async requestPasswordReset(identifier: string): Promise<void> {
    await api.post('/auth/request-reset', { identifier });
  },

  logout() {
    authStore.clearSession();
    window.location.href = '/login';
  },
};
