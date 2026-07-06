import { api } from '@mesiri/auth';

export type AccessMode = 'all_projects' | 'custom_projects';
export type SiteAccessMode = 'all_sites' | 'custom_sites';

export interface ProjectAccess {
  projectId: string;
  siteAccess: {
    mode: SiteAccessMode;
    siteIds?: string[];
  };
}

export interface UserAccessPolicy {
  mode: AccessMode;
  projects?: ProjectAccess[];
}

export interface UserDetails {
  id: string;
  full_name: string;
  email: string;
  role: string;
  status: 'active' | 'inactive' | 'suspended' | 'invited';
  whatsapp_number?: string | null;
  accessPolicy: UserAccessPolicy;
}

export const userAccessService = {
  async getUserDetails(userId: string): Promise<UserDetails> {
    const { data } = await api.get(`/users/${userId}`);
    return {
      id: data.id,
      full_name: data.full_name,
      email: data.email,
      role: data.role,
      status: data.status ?? 'active',
      whatsapp_number: data.whatsapp_number ?? null,
      accessPolicy: data.access_policy ?? { mode: 'custom_projects', projects: [] },
    };
  },

  async updateUserRole(userId: string, role: string): Promise<void> {
    await api.patch(`/users/${userId}`, { role });
  },

  async updateUserStatus(userId: string, status: string): Promise<void> {
    await api.patch(`/users/${userId}/status`, { status });
  },

  async updateUserAccessPolicy(userId: string, policy: UserAccessPolicy): Promise<void> {
    await api.put(`/users/${userId}/access`, policy);
  },
};
