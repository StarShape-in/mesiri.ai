import { api } from '@mesiri/auth';

export interface MaterialReceipt {
  id: string;
  organizationId: string;
  projectId: string;
  siteId: string | null;
  materialName: string;
  quantity: number;
  unit: string;
  unitCost: number | null;
  totalCost: number | null;
  supplier: string | null;
  occurredDate: string;
  occurredTime: string | null;
  correlationId: string | null;
  source: string;
  occurredDateSource: string;
  materialId: string | null;
  createdAt: string;
  createdBy: string;
  updatedAt: string;
  updatedBy: string | null;
}

export interface MaterialUsage {
  id: string;
  organizationId: string;
  projectId: string;
  siteId: string | null;
  materialName: string;
  quantity: number;
  unit: string;
  workItem: string | null;
  occurredDate: string;
  occurredTime: string | null;
  correlationId: string | null;
  source: string;
  occurredDateSource: string;
  materialId: string | null;
  createdAt: string;
  createdBy: string;
  updatedAt: string;
  updatedBy: string | null;
}

export interface MaterialStock {
  organizationId: string;
  projectId: string;
  siteId: string | null;
  materialName: string;
  unit: string;
  totalReceived: number;
  totalUsed: number;
  currentStock: number;
}

export interface InflowsQueryParams {
  project_id?: string;
  site_id?: string;
  material_name?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}

export interface OutflowsQueryParams {
  project_id?: string;
  site_id?: string;
  material_name?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}

export interface InventoryQueryParams {
  project_id?: string;
  site_id?: string;
}

export const materialsService = {
  async getInflows(params: InflowsQueryParams): Promise<{ items: MaterialReceipt[]; total: number }> {
    const { data } = await api.get('/materials/inflows', { params });
    const items = (data.items || []).map((item: any) => ({
      id: item.id,
      organizationId: item.organization_id,
      projectId: item.project_id,
      siteId: item.site_id,
      materialName: item.material_name,
      quantity: Number(item.quantity),
      unit: item.unit,
      unitCost: item.unit_cost !== null ? Number(item.unit_cost) : null,
      totalCost: item.total_cost !== null ? Number(item.total_cost) : null,
      supplier: item.supplier,
      occurredDate: item.occurred_date,
      occurredTime: item.occurred_time,
      correlationId: item.correlation_id,
      source: item.source,
      occurredDateSource: item.occurred_date_source,
      materialId: item.material_id,
      createdAt: item.created_at,
      createdBy: item.created_by,
      updatedAt: item.updated_at,
      updatedBy: item.updated_by,
    }));
    return { items, total: data.total || 0 };
  },

  async getOutflows(params: OutflowsQueryParams): Promise<{ items: MaterialUsage[]; total: number }> {
    const { data } = await api.get('/materials/outflows', { params });
    const items = (data.items || []).map((item: any) => ({
      id: item.id,
      organizationId: item.organization_id,
      projectId: item.project_id,
      siteId: item.site_id,
      materialName: item.material_name,
      quantity: Number(item.quantity),
      unit: item.unit,
      workItem: item.work_item,
      occurredDate: item.occurred_date,
      occurredTime: item.occurred_time,
      correlationId: item.correlation_id,
      source: item.source,
      occurredDateSource: item.occurred_date_source,
      materialId: item.material_id,
      createdAt: item.created_at,
      createdBy: item.created_by,
      updatedAt: item.updated_at,
      updatedBy: item.updated_by,
    }));
    return { items, total: data.total || 0 };
  },

  async getInventory(params: InventoryQueryParams): Promise<MaterialStock[]> {
    const { data } = await api.get('/materials/inventory', { params });
    return (data || []).map((item: any) => ({
      organizationId: item.organization_id,
      projectId: item.project_id,
      siteId: item.site_id,
      materialName: item.material_name,
      unit: item.unit,
      totalReceived: Number(item.total_received),
      totalUsed: Number(item.total_used),
      currentStock: Number(item.current_stock),
    }));
  },
};
