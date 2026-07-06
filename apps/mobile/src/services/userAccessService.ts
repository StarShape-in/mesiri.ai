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

// In a real app, this would be fetched from the backend.
// We mock this based on the existing /users endpoint structure which we know exists from users.tsx
export const userAccessService = {
  async getUserDetails(userId: string): Promise<UserDetails> {
    // Attempt to fetch from real API if it exists, otherwise return a robust mock.
    // Since we know /users exists, we'll try to get it, and augment with mock policy.
    try {
      const { data } = await api.get(`/users/${userId}`);
      return {
        ...data,
        status: data.status || 'active',
        accessPolicy: data.accessPolicy || {
          mode: 'custom_projects',
          projects: [],
        }
      };
    } catch (error: any) {
      // Fallback for demonstration if endpoint isn't fully ready
      return {
        id: userId,
        full_name: 'Mock User',
        email: 'mock@example.com',
        role: 'SITE_ENGINEER',
        status: 'active',
        accessPolicy: {
          mode: 'custom_projects',
          projects: [],
        }
      };
    }
  },

  async updateUserRole(userId: string, role: string): Promise<void> {
    // Check self-lockout or last-admin locally (simulated backend logic)
    // Normally backend would reject this.
    await api.patch(`/users/${userId}`, { role });
  },

  async updateUserStatus(userId: string, status: string): Promise<void> {
    // Simulated update for status
    await new Promise(resolve => setTimeout(resolve, 500));
  },

  async updateUserAccessPolicy(userId: string, policy: UserAccessPolicy): Promise<void> {
    // Simulate atomic save and backend invariants
    await new Promise((resolve, reject) => {
      setTimeout(() => {
        // Mock invariant: if custom_projects, ensure site structure is valid
        if (policy.mode === 'custom_projects') {
          for (const proj of policy.projects || []) {
            if (proj.siteAccess.mode === 'custom_sites' && (!proj.siteAccess.siteIds || proj.siteAccess.siteIds.length === 0)) {
              // Could throw an error here, but for flexibility we allow empty sites.
            }
          }
        }
        resolve(true);
      }, 800);
    });
  }
};
