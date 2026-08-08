import { api, ApiResponse } from '@/lib/api';

export type DriverStatus = 'Available' | 'OnTrip' | 'OffDuty' | 'Inactive';

export interface Driver {
  id: string;
  ref_id: string | null;
  first_name: string;
  last_name: string;
  phone_primary: string;
  status: DriverStatus;
  license_number: string;
  license_expiry: string;
  ai_risk_score: number;
  isActive: boolean;
  createdAt: string;
  trips?: any[];
  documents?: Document[];
}

export interface CreateDriverPayload {
  first_name: string;
  last_name: string;
  phone_primary: string;
  license_number: string;
  license_expiry: string;
}

export interface DriverFilters {
  status?: DriverStatus;
  search?: string;
  page?: number;
  per_page?: number;
}

export const driverService = {
  async getAll(filters: DriverFilters = {}): Promise<ApiResponse<Driver[]>> {
    const res = await api.get<ApiResponse<Driver[]>>('/drivers', { params: filters });
    return res.data;
  },

  async getById(id: string): Promise<Driver> {
    const res = await api.get<ApiResponse<Driver>>(`/drivers/${id}`);
    return res.data.data;
  },

  async create(payload: CreateDriverPayload): Promise<Driver> {
    const res = await api.post<ApiResponse<Driver>>('/drivers', payload);
    return res.data.data;
  },

  async update(id: string, payload: Partial<CreateDriverPayload & { status: DriverStatus }>): Promise<Driver> {
    const res = await api.patch<ApiResponse<Driver>>(`/drivers/${id}`, payload);
    return res.data.data;
  },

  async delete(id: string, password?: string): Promise<void> {
    await api.delete(`/drivers/${id}`, { data: { password } });
  },

  async bulkDelete(ids: string[]): Promise<void> {
    await api.post('/drivers/bulk-delete', { ids });
  },

  async bulkUpdateStatus(ids: string[], status: string): Promise<void> {
    await api.post('/drivers/bulk-update-status', { ids, status });
  },
};
