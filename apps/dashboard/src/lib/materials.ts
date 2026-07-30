import { api } from './api'

// Typed boundary for the /materials domain — Material catalog, Inflows
// (receipts), Outflows (usage), aggregated Inventory, and the per-site,
// per-material movement Ledger. See backend/src/mesiri/domains/materials
// for the source of truth on shapes and authorization rules.

export interface MaterialCatalog {
  id: string
  organization_id: string
  name: string
  default_unit: string | null
  // The material's Stock Unit — every receipt/outflow for this material must
  // use this unit_id; no unit conversion, and it can't change once the
  // material has any recorded movement (see backend PATCH /materials/{id}).
  default_unit_id: string
  category: string | null
  sku: string | null
  is_active: boolean
}

export interface MaterialCatalogListResponse {
  items: MaterialCatalog[]
  total: number
}

export interface UnitOfMeasure {
  id: string
  code: string
  display_name: string
  is_active: boolean
}

export interface UnitsOfMeasureListResponse {
  items: UnitOfMeasure[]
}

export type InflowReason = 'RECEIVED' | 'TRANSFER_IN' | 'RETURN_IN' | 'ADJUSTMENT_IN'
export type OutflowReason = 'CONSUMED' | 'TRANSFER_OUT' | 'RETURN_TO_VENDOR' | 'WASTAGE' | 'ADJUSTMENT_OUT'

export interface MaterialReceipt {
  id: string
  organization_id: string
  project_id: string
  site_id: string | null
  material_name: string
  quantity: string
  unit: string
  unit_id: string
  unit_cost: string | null
  total_cost: string | null
  supplier: string | null
  occurred_date: string
  occurred_time: string | null
  correlation_id: string | null
  source: string
  occurred_date_source: string | null
  material_id: string | null
  movement_reason: InflowReason
  notes: string | null
  reverses_movement_id: string | null
  // Only populated by the detail endpoints — a correction has already been
  // posted against this movement, so offering "Correct" again would 409.
  already_reversed?: boolean
  created_at: string
  created_by: string | null
  updated_at: string | null
  updated_by: string | null
}

export interface MaterialUsage {
  id: string
  organization_id: string
  project_id: string
  site_id: string | null
  material_name: string
  quantity: string
  unit: string
  unit_id: string
  work_item: string | null
  occurred_date: string
  occurred_time: string | null
  correlation_id: string | null
  source: string
  occurred_date_source: string | null
  material_id: string | null
  movement_reason: OutflowReason
  notes: string | null
  reverses_movement_id: string | null
  // Only populated by the detail endpoints — a correction has already been
  // posted against this movement, so offering "Correct" again would 409.
  already_reversed?: boolean
  created_at: string
  created_by: string | null
  updated_at: string | null
  updated_by: string | null
}

// Client-side merged shape for "one movement" rendering (used by the
// details sheet caller and any UI that treats inflow/outflow uniformly).
export type MaterialMovement =
  | ({ direction: 'IN' } & MaterialReceipt)
  | ({ direction: 'OUT' } & MaterialUsage)

export interface MaterialMovementListResponse<T> {
  items: T[]
  total: number
}

export interface MovementFilters {
  project_id?: string
  site_id?: string
  material_id?: string
  material_name?: string
  movement_reason?: string
  source?: string
  recorded_by_user_id?: string
  date_from?: string
  date_to?: string
  limit?: number
  offset?: number
}

export type StockState = 'AVAILABLE' | 'OUT_OF_STOCK' | 'NEGATIVE_STOCK'

export interface MaterialStock {
  organization_id: string
  project_id: string
  site_id: string
  material_id: string
  material_name: string
  unit: string
  total_received: string
  total_used: string
  current_stock: string
  last_movement_at: string | null
  stock_state: StockState
}

export interface LedgerEntry {
  id: string
  direction: 'IN' | 'OUT'
  movement_reason: string
  quantity: string
  unit: string
  occurred_date: string
  occurred_time: string | null
  source: string
  notes: string | null
  context: string | null
  reverses_movement_id: string | null
  created_by: string | null
  created_at: string
  running_balance: string
}

export interface LedgerResponse {
  items: LedgerEntry[]
  total: number
  current_balance: string
  unit: string
}

// ---------------------------------------------------------------------
// Material catalog
// ---------------------------------------------------------------------

export interface MaterialCatalogFilters {
  search?: string
  is_active?: boolean
  limit?: number
  offset?: number
}

export async function fetchMaterials(
  filters: MaterialCatalogFilters = {}
): Promise<MaterialCatalogListResponse> {
  const res = await api.get<MaterialCatalogListResponse>('/materials', { params: filters })
  return res.data
}

export async function fetchMaterial(id: string): Promise<MaterialCatalog> {
  const res = await api.get<MaterialCatalog>(`/materials/${id}`)
  return res.data
}

export async function createMaterial(payload: {
  name: string
  default_unit_id: string
  category?: string
  sku?: string
}): Promise<MaterialCatalog> {
  const res = await api.post<MaterialCatalog>('/materials', payload)
  return res.data
}

export async function updateMaterial(
  id: string,
  payload: {
    name?: string
    default_unit_id?: string
    category?: string
    sku?: string
    is_active?: boolean
  }
): Promise<MaterialCatalog> {
  const res = await api.patch<MaterialCatalog>(`/materials/${id}`, payload)
  return res.data
}

export async function deleteMaterial(id: string): Promise<void> {
  await api.delete(`/materials/${id}`)
}

export async function setMaterialActive(id: string, isActive: boolean): Promise<MaterialCatalog> {
  return updateMaterial(id, { is_active: isActive })
}

export async function fetchUnitsOfMeasure(): Promise<UnitsOfMeasureListResponse> {
  const res = await api.get<UnitsOfMeasureListResponse>('/materials/units-of-measure')
  return res.data
}

// ---------------------------------------------------------------------
// Inflows (receipts)
// ---------------------------------------------------------------------

export async function fetchInflows(
  filters: MovementFilters = {}
): Promise<MaterialMovementListResponse<MaterialReceipt>> {
  const res = await api.get<MaterialMovementListResponse<MaterialReceipt>>('/materials/inflows', {
    params: filters,
  })
  return res.data
}

export async function fetchInflow(id: string): Promise<MaterialReceipt> {
  const res = await api.get<MaterialReceipt>(`/materials/inflows/${id}`)
  return res.data
}

export interface CreateInflowPayload {
  project_id: string
  site_id?: string
  material_id: string
  unit_id: string
  quantity: string | number
  movement_reason?: InflowReason
  supplier?: string
  notes?: string
  occurred_date: string
}

// A retried request must not become a second delivery. The key is generated
// once when a record dialog opens and reused for every submit attempt from
// that dialog, so a double tap or a resend after a timeout replays the first
// result instead of recording again. See the backend's _claim_idempotency_key.
export function newIdempotencyKey(): string {
  return crypto.randomUUID()
}

function idempotencyHeaders(key?: string) {
  return key ? { headers: { 'Idempotency-Key': key } } : undefined
}

export async function createInflow(
  payload: CreateInflowPayload,
  idempotencyKey?: string
): Promise<{ id: string; status: string }> {
  const res = await api.post<{ id: string; status: string }>(
    '/materials/inflows',
    payload,
    idempotencyHeaders(idempotencyKey)
  )
  return res.data
}

export async function reverseInflow(
  id: string,
  payload: { reason_note?: string; occurred_date?: string } = {}
): Promise<{ id: string; status: string }> {
  const res = await api.post<{ id: string; status: string }>(`/materials/inflows/${id}/reverse`, payload)
  return res.data
}

// ---------------------------------------------------------------------
// Outflows (usage)
// ---------------------------------------------------------------------

export async function fetchOutflows(
  filters: MovementFilters = {}
): Promise<MaterialMovementListResponse<MaterialUsage>> {
  const res = await api.get<MaterialMovementListResponse<MaterialUsage>>('/materials/outflows', {
    params: filters,
  })
  return res.data
}

export async function fetchOutflow(id: string): Promise<MaterialUsage> {
  const res = await api.get<MaterialUsage>(`/materials/outflows/${id}`)
  return res.data
}

export interface CreateOutflowPayload {
  project_id: string
  site_id?: string
  material_id: string
  unit_id: string
  quantity: string | number
  movement_reason?: OutflowReason
  work_item?: string
  notes?: string
  occurred_date: string
  // Send false to have the backend refuse an issue that would take stock
  // below zero (it returns a 409 carrying the real balance). Defaults to true
  // server-side so WhatsApp and mobile are unaffected; the dashboard opts in
  // and turns the refusal into a confirmation.
  allow_negative?: boolean
}

export async function createOutflow(
  payload: CreateOutflowPayload,
  idempotencyKey?: string
): Promise<{ id: string; status: string }> {
  const res = await api.post<{ id: string; status: string }>(
    '/materials/outflows',
    payload,
    idempotencyHeaders(idempotencyKey)
  )
  return res.data
}

export interface StockCheck {
  material_id: string
  site_id: string | null
  available: string
  unit: string | null
}

// The balance the backend's own guard will use, so the dialog can warn before
// submitting rather than after a rejection.
export async function fetchStockCheck(
  materialId: string,
  siteId?: string | null
): Promise<StockCheck> {
  const res = await api.get<StockCheck>('/materials/stock-check', {
    params: { material_id: materialId, site_id: siteId ?? undefined },
  })
  return res.data
}

// Shape of the 409 body the outflow endpoint returns when a quantity exceeds
// available stock and allow_negative was not set.
export interface OverStockConflict {
  message: string
  available: string
  requested: string
  unit: string
  material_name: string
}

export function asOverStockConflict(err: any): OverStockConflict | null {
  const detail = err?.response?.data?.detail
  if (err?.response?.status === 409 && detail && typeof detail === 'object' && 'available' in detail) {
    return detail as OverStockConflict
  }
  return null
}

export async function reverseOutflow(
  id: string,
  payload: { reason_note?: string; occurred_date?: string } = {}
): Promise<{ id: string; status: string }> {
  const res = await api.post<{ id: string; status: string }>(`/materials/outflows/${id}/reverse`, payload)
  return res.data
}

// ---------------------------------------------------------------------
// Inventory + Ledger
// ---------------------------------------------------------------------

export interface InventoryFilters {
  project_id?: string
  site_id?: string
  material_id?: string
}

export async function fetchInventory(filters: InventoryFilters = {}): Promise<MaterialStock[]> {
  const res = await api.get<MaterialStock[]>('/materials/inventory', { params: filters })
  return res.data
}

export async function fetchLedger(
  siteId: string,
  materialId: string,
  params: { limit?: number; offset?: number } = {}
): Promise<LedgerResponse> {
  const res = await api.get<LedgerResponse>(`/materials/ledger/${siteId}/${materialId}`, { params })
  return res.data
}

// Reasons that require ADMIN/PROJECT_MANAGER to submit — see backend
// authorization rules on POST /materials/inflows and /materials/outflows.
export const ADJUSTMENT_REASONS = new Set(['ADJUSTMENT_IN', 'ADJUSTMENT_OUT'])

export const INFLOW_REASONS: Array<{ value: InflowReason; label: string }> = [
  { value: 'RECEIVED', label: 'Received' },
  { value: 'TRANSFER_IN', label: 'Transfer In' },
  { value: 'RETURN_IN', label: 'Return In' },
  { value: 'ADJUSTMENT_IN', label: 'Adjustment In' },
]

export const OUTFLOW_REASONS: Array<{ value: OutflowReason; label: string }> = [
  { value: 'CONSUMED', label: 'Consumed' },
  { value: 'TRANSFER_OUT', label: 'Transfer Out' },
  { value: 'RETURN_TO_VENDOR', label: 'Return To Vendor' },
  { value: 'WASTAGE', label: 'Wastage' },
  { value: 'ADJUSTMENT_OUT', label: 'Adjustment Out' },
]
