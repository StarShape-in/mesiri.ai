import { api, ApiResponse } from '@/lib/api';

export type InvoiceStatus = 'Draft' | 'Pending' | 'Paid' | 'Overdue' | 'Cancelled';

export interface Invoice {
  id: string;
  ref_id: string | null;
  status: InvoiceStatus;
  currency: string;
  subtotal: number;
  total_amount: number;
  due_date: string;
  createdAt: string;
  customer?: { id: string; name: string };
  trip?: { id: string; ref_id: string; status: string };
}

export interface CreateInvoicePayload {
  trip_id: string;
  customer_id: string;
  subtotal: number;
  total_amount: number;
  due_date: string;
}

export interface InvoiceFilters {
  status?: InvoiceStatus;
  customer_id?: string;
  search?: string;
  page?: number;
  per_page?: number;
}

export const invoiceService = {
  async getAll(filters: InvoiceFilters = {}): Promise<ApiResponse<Invoice[]>> {
    const res = await api.get<ApiResponse<Invoice[]>>('/invoices', { params: filters });
    return res.data;
  },

  async getById(id: string): Promise<Invoice> {
    const res = await api.get<ApiResponse<Invoice>>(`/invoices/${id}`);
    return res.data.data;
  },

  async create(payload: CreateInvoicePayload): Promise<Invoice> {
    const res = await api.post<ApiResponse<Invoice>>('/invoices', payload);
    return res.data.data;
  },

  async updateStatus(id: string, status: InvoiceStatus): Promise<Invoice> {
    const res = await api.patch<ApiResponse<Invoice>>(`/invoices/${id}/status`, { status });
    return res.data.data;
  },

  async bulkDelete(ids: string[]): Promise<void> {
    await api.post('/invoices/bulk-delete', { ids });
  },

  async bulkUpdateStatus(ids: string[], status: string): Promise<void> {
    await api.post('/invoices/bulk-update-status', { ids, status });
  },
};
