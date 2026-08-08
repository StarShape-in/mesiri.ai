import { api, ApiResponse } from '@/lib/api';

export interface Customer {
  id: string;
  name: string;
  contact_phone: string;
  credit_limit: number;
  isActive: boolean;
  createdAt: string;
  default_pickup_lat?: number | null;
  default_pickup_lng?: number | null;
  default_dropoff_lat?: number | null;
  default_dropoff_lng?: number | null;
  trips?: { id: string; ref_id: string; status: string; createdAt: string }[];
}

export interface CreateCustomerPayload {
  name: string;
  contact_phone: string;
  credit_limit?: number;
  default_pickup_lat?: number | null;
  default_pickup_lng?: number | null;
  default_dropoff_lat?: number | null;
  default_dropoff_lng?: number | null;
}

export interface CustomerFilters {
  search?: string;
  is_active?: boolean;
  page?: number;
  per_page?: number;
}

export const customerService = {
  async getAll(filters: CustomerFilters = {}): Promise<ApiResponse<Customer[]>> {
    const res = await api.get<ApiResponse<Customer[]>>('/customers', { params: filters });
    return res.data;
  },

  async getById(id: string): Promise<Customer> {
    const res = await api.get<ApiResponse<Customer>>(`/customers/${id}`);
    return res.data.data;
  },

  async create(payload: CreateCustomerPayload): Promise<Customer> {
    const res = await api.post<ApiResponse<Customer>>('/customers', payload);
    return res.data.data;
  },

  async update(id: string, payload: Partial<CreateCustomerPayload>): Promise<Customer> {
    const res = await api.patch<ApiResponse<Customer>>(`/customers/${id}`, payload);
    return res.data.data;
  },

  async delete(id: string): Promise<void> {
    await api.delete(`/customers/${id}`);
  },
};
