import { api, ApiResponse } from '@/lib/api';

export type AssetStatus = 'Available' | 'OnTrip' | 'Maintenance' | 'Inactive';
export type AssetType   = 'Flatbed' | 'Reefer' | 'Box' | 'Tanker';

export interface Vehicle {
  id: string;
  ref_id: string | null;
  plate_number: string;
  asset_type: AssetType;
  status: AssetStatus;
  capacity_kg: number;
  current_odometer: number;
  gps_device_id: string | null;
  trailer_number: string | null;
  trailer_type: AssetType | null;
  trailer_capacity_kg: number | null;
  icces_device_id: string | null;
  isActive: boolean;
  createdAt: string;
  documents?: import('./documentService').MerconDocument[];
  trips?: any[];
}

export interface CreateVehiclePayload {
  plate_number: string;
  asset_type: AssetType;
  capacity_kg: number;
  trailer_number?: string;
  trailer_type?: AssetType;
  trailer_capacity_kg?: number;
  gps_device_id?: string;
  icces_device_id?: string;
}

export interface VehicleFilters {
  status?: AssetStatus;
  search?: string;
  page?: number;
  per_page?: number;
}

export interface VehicleFinancials {
  vehicle_id: string;
  plate_number: string;
  ref_id: string | null;
  asset_type: AssetType;
  summary: {
    total_income: number;
    total_expenses: number;
    maintenance_expenses: number;
    renewal_expenses: number;
    net_profit: number;
    margin_percent: number;
    completed_trips_count: number;
    total_maintenance_count: number;
  };
  income_sources: Array<{
    id: string;
    ref_id: string | null;
    status: string;
    customer_name: string;
    cargo_type: string;
    date: string;
    income: number;
  }>;
  expense_records: import('./maintenanceService').MaintenanceRecord[];
}

export const vehicleService = {
  async getAll(filters: VehicleFilters = {}): Promise<ApiResponse<Vehicle[]>> {
    const res = await api.get<ApiResponse<Vehicle[]>>('/vehicles', { params: filters });
    return res.data;
  },

  async getById(id: string): Promise<Vehicle> {
    const res = await api.get<ApiResponse<Vehicle>>(`/vehicles/${id}`);
    return res.data.data;
  },

  async getFinancials(id: string): Promise<VehicleFinancials> {
    const res = await api.get<ApiResponse<VehicleFinancials>>(`/vehicles/${id}/financials`);
    return res.data.data;
  },

  async create(payload: CreateVehiclePayload): Promise<Vehicle> {
    const res = await api.post<ApiResponse<Vehicle>>('/vehicles', payload);
    return res.data.data;
  },

  async update(id: string, payload: Partial<CreateVehiclePayload & { status: AssetStatus }>): Promise<Vehicle> {
    const res = await api.patch<ApiResponse<Vehicle>>(`/vehicles/${id}`, payload);
    return res.data.data;
  },

  async delete(id: string): Promise<void> {
    await api.delete(`/vehicles/${id}`);
  },

  async bulkDelete(ids: string[]): Promise<void> {
    await api.post('/vehicles/bulk-delete', { ids });
  },

  async bulkUpdateStatus(ids: string[], status: string): Promise<void> {
    await api.post('/vehicles/bulk-update-status', { ids, status });
  },
};
