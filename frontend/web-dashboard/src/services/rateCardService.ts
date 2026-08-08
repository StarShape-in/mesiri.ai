import { api, ApiResponse } from '@/lib/api';

export interface RateCard {
  id: string;
  name: string;
  route_origin: string;
  route_destination: string;
  base_price: number;
  currency: string;
  customerId: string;
  is_active: boolean;
  createdAt: string;
  updatedAt: string;
  customer?: { id: string; name: string };
}

export interface CreateRateCardPayload {
  name: string;
  route_origin: string;
  route_destination: string;
  base_price: number;
  currency: string;
  customerId: string;
}

export const rateCardService = {
  async getAll(): Promise<ApiResponse<RateCard[]>> {
    const res = await api.get<ApiResponse<RateCard[]>>('/rate-cards');
    return res.data;
  },

  async getById(id: string): Promise<RateCard> {
    const res = await api.get<ApiResponse<RateCard>>(`/rate-cards/${id}`);
    return res.data.data;
  },

  async create(payload: CreateRateCardPayload): Promise<RateCard> {
    const res = await api.post<ApiResponse<RateCard>>('/rate-cards', payload);
    return res.data.data;
  },

  async update(id: string, payload: Partial<CreateRateCardPayload & { is_active: boolean }>): Promise<RateCard> {
    const res = await api.put<ApiResponse<RateCard>>(`/rate-cards/${id}`, payload);
    return res.data.data;
  },

  async delete(id: string): Promise<void> {
    await api.delete(`/rate-cards/${id}`);
  },

  async bulkDelete(ids: string[]): Promise<void> {
    await api.post('/rate-cards/bulk-delete', { ids });
  },
};
