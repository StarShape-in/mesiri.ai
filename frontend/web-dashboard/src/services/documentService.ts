import { api, ApiResponse } from '@/lib/api';

export type DocType   = 'DriverLicense' | 'VehicleRegistration' | 'Insurance' | 'POD' | 'CustomsClearance' | 'Waybill' | 'Contract' | 'Invoice';
export type DocStatus = 'PendingReview' | 'Verified' | 'Rejected' | 'Expired';

export interface MerconDocument {
  id: string;
  entity_type: string;
  entity_id: string;
  doc_type: DocType;
  status: DocStatus;
  file_url: string;
  mime_type: string | null;
  issue_date: string | null;
  expiry_date: string | null;
  is_confidential: boolean;
  isActive: boolean;
  createdAt: string;
}

export interface DocumentFilters {
  entity_type?: string;
  entity_id?: string;
  doc_type?: DocType;
  status?: DocStatus;
  expiring_within_days?: number;
  page?: number;
  per_page?: number;
}

export const documentService = {
  async getAll(filters: DocumentFilters = {}): Promise<ApiResponse<MerconDocument[]>> {
    const res = await api.get<ApiResponse<MerconDocument[]>>('/documents', { params: filters });
    return res.data;
  },

  async getById(id: string): Promise<MerconDocument> {
    const res = await api.get<ApiResponse<MerconDocument>>(`/documents/${id}`);
    return res.data.data;
  },

  async upload(formData: FormData): Promise<MerconDocument> {
    const res = await api.post<ApiResponse<MerconDocument>>('/documents', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data.data;
  },

  async updateStatus(id: string, status: DocStatus, expiry_date?: string): Promise<MerconDocument> {
    const res = await api.patch<ApiResponse<MerconDocument>>(`/documents/${id}/status`, { status, expiry_date });
    return res.data.data;
  },

  async delete(id: string): Promise<void> {
    await api.delete(`/documents/${id}`);
  },

  async bulkDelete(ids: string[]): Promise<void> {
    await api.post('/documents/bulk-delete', { ids });
  },

  async bulkUpdateStatus(ids: string[], status: string): Promise<void> {
    await api.post('/documents/bulk-update-status', { ids, status });
  },
};
