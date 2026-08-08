import { api, ApiResponse } from '@/lib/api';

export interface Notification {
  id: string;
  title: string;
  message: string;
  type: string;
  is_read: boolean;
  entity_type?: string | null;
  entity_id?: string | null;
  createdAt: string;
}

export const notificationService = {
  async getAll(): Promise<ApiResponse<Notification[]>> {
    const res = await api.get<ApiResponse<Notification[]>>('/notifications');
    return res.data;
  },

  async markAsRead(id: string): Promise<void> {
    await api.patch(`/notifications/${id}/read`);
  },

  async sendBulkCommunication(payload: { entity_type: string, ids: string[], method: 'email' | 'sms', subject: string, message: string }): Promise<void> {
    await api.post('/notifications/bulk-send', payload);
  }
};
