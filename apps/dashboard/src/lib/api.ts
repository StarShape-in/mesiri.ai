import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const TOKEN_KEY = 'mesiri_dashboard_token'

export const api = axios.create({ baseURL: BASE_URL })

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// A token in localStorage is not proof of a valid session — it may be
// expired, malformed, or revoked. Any 401/403 from the backend (the real
// authorization boundary) clears the stale token and bounces to /login.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 || error.response?.status === 403) {
      clearToken()
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export type AccessPolicy = {
  mode: 'all_projects' | 'custom_projects'
  projects: Array<{
    projectId: string
    siteAccess?: { mode: 'all_sites' | 'custom_sites'; siteIds?: string[] }
  }>
}

export interface Me {
  user_id: string
  organization_id: string
  organization_name: string | null
  role: string
  full_name: string
  access_policy: AccessPolicy
}

export async function login(email: string, password: string): Promise<void> {
  const res = await api.post('/auth/login', { email, password })
  setToken(res.data.access_token)
}

export async function logout(): Promise<void> {
  clearToken()
}

export async function fetchMe(): Promise<Me> {
  const res = await api.get<Me>('/auth/me')
  return res.data
}

export interface User {
  id: string
  email: string
  full_name: string
  role: 'ADMIN' | 'PROJECT_MANAGER' | 'SITE_ENGINEER' | 'FINANCE'
  whatsapp_number?: string | null
  status: 'active' | 'inactive' | 'suspended' | 'invited'
  access_policy?: AccessPolicy | null
}

export interface UserCreatePayload {
  full_name: string
  email: string
  password?: string
  role: string
  whatsapp_number?: string | null
}

export interface UserUpdatePayload {
  full_name?: string
  role?: string
  whatsapp_number?: string | null
  password?: string
}

export async function fetchUsers(): Promise<User[]> {
  const res = await api.get<User[]>('/users')
  return res.data
}

export async function fetchUser(userId: string): Promise<User> {
  const res = await api.get<User>(`/users/${userId}`)
  return res.data
}

export async function createUser(payload: UserCreatePayload): Promise<User> {
  const res = await api.post<User>('/users', payload)
  return res.data
}

export async function updateUser(userId: string, payload: UserUpdatePayload): Promise<User> {
  const res = await api.patch<User>(`/users/${userId}`, payload)
  return res.data
}

export async function updateUserStatus(userId: string, status: string): Promise<User> {
  const res = await api.patch<User>(`/users/${userId}/status`, { status })
  return res.data
}

export async function fetchUserAccess(userId: string): Promise<AccessPolicy> {
  const res = await api.get<AccessPolicy>(`/users/${userId}/access`)
  return res.data
}

export async function updateUserAccess(userId: string, policy: AccessPolicy): Promise<AccessPolicy> {
  const res = await api.put<AccessPolicy>(`/users/${userId}/access`, policy)
  return res.data
}

export async function deleteUser(userId: string): Promise<void> {
  await api.delete(`/users/${userId}`)
}

export interface Company {
  id: string
  name: string
  deployment_type: string
  db_route: string
  status: string
  code?: string | null
  email?: string | null
  phone?: string | null
  address?: string | null
  primary_contact?: string | null
  timezone: string
  created_at: string
  updated_at: string
}

export interface CompanySummary {
  total_users: number
  active_users: number
  admin_count: number
  pm_count: number
  site_engineer_count: number
  finance_count: number
  total_projects: number
  total_sites: number
  wa_mapped_users: number
  wa_unmapped_users: number
  active_conversations_count: number
  messages_received_today: number
  messages_requiring_clarification: number
  last_whatsapp_activity?: string | null
}

export interface MessageMinUser {
  id: string
  email: string
  full_name: string
  role: string
  status: string
  whatsapp_number?: string | null
}

export interface CompanyMessage {
  id: string
  correlation_id: string
  direction: 'inbound' | 'outbound'
  sender_wa_id: string
  message_type: string
  body: string
  processing_status: string
  error_code?: string | null
  timestamp: string
  member?: MessageMinUser | null
  project_id?: string | null
  project_name?: string | null
  site_id?: string | null
  site_name?: string | null
}

export interface CompanyMessageList {
  items: CompanyMessage[]
  total: number
}

export interface JourneyTrace {
  stage: string
  succeeded: boolean
  duration_ms?: number | null
  error_code?: string | null
  error_message?: string | null
  created_at: string
}

export interface ProviderExecution {
  stage: string
  provider: string
  operation: string
  model?: string | null
  latency_ms?: number | null
  succeeded: boolean
  created_at: string
}

export interface TimelineEntryMin {
  id: string
  event_type: string
  summary: string
  source_aggregate_type: string
  source_aggregate_id: string
  occurred_at: string
}

export interface InteractionMin {
  id: string
  kind: string
  prompt: string
  status: string
  created_at: string
  resolved_at?: string | null
}

export interface CompanyMessageDetail extends CompanyMessage {
  body_text?: string | null
  raw_payload_captured: boolean
  assistant_reply?: string | null
  raw_payload?: any | null
  normalized_message?: any | null
  media_object_key?: string | null
  received_at: string
  processed_at?: string | null
  traces: JourneyTrace[]
  providers: ProviderExecution[]
  timeline_entries: TimelineEntryMin[]
  interactions: InteractionMin[]
}


export async function fetchCompany(): Promise<Company> {
  const res = await api.get<Company>('/company')
  return res.data
}

export async function updateCompany(payload: Partial<Company>): Promise<Company> {
  const res = await api.patch<Company>('/company', payload)
  return res.data
}

export async function fetchCompanySummary(): Promise<CompanySummary> {
  const res = await api.get<CompanySummary>('/company/summary')
  return res.data
}

export interface FetchMessagesParams {
  direction?: string
  search?: string
  member_id?: string
  message_type?: string
  project_id?: string
  site_id?: string
  processing_status?: string
  has_attachments?: boolean
  mapped_participant?: string
  limit?: number
  offset?: number
}

export async function fetchCompanyMessages(params?: FetchMessagesParams): Promise<CompanyMessageList> {
  const res = await api.get<CompanyMessageList>('/company/whatsapp/messages', { params })
  return res.data
}

export async function fetchCompanyMessageDetail(messageId: string): Promise<CompanyMessageDetail> {
  const res = await api.get<CompanyMessageDetail>(`/company/whatsapp/messages/${messageId}`)
  return res.data
}

export async function fetchConversationMessages(conversationId: string): Promise<CompanyMessage[]> {
  const res = await api.get<CompanyMessage[]>(`/company/whatsapp/conversations/${conversationId}/messages`)
  return res.data
}


export interface MessageOutcome {
  record_type: string
  record_id: string
  summary: string
}

export interface MessageProject {
  id: string
  name: string
}

export interface MessageSite {
  id: string
  name: string
}

export interface UserWhatsAppMessage {
  id: string
  correlation_id: string
  sender_wa_id: string
  message_type: string
  body_text?: string | null
  media_object_key?: string | null
  occurred_at: string
  direction: 'inbound' | 'outbound'
  processing_status: string
  error_code?: string | null
  clarification_status: 'none' | 'awaiting_user' | 'resolved' | 'expired'
  project?: MessageProject | null
  site?: MessageSite | null
  outcome?: MessageOutcome | null
}

export interface UserWhatsAppMessageList {
  items: UserWhatsAppMessage[]
  total: number
}

export interface MessageTrace {
  stage: string
  succeeded: boolean
  duration_ms?: number | null
  error_code?: string | null
  error_message?: string | null
  severity: string
  event_source: string
  created_at: string
}

export interface MessageProviderExecution {
  stage: string
  provider: string
  operation: string
  model?: string | null
  latency_ms?: number | null
  succeeded: boolean
  error_code?: string | null
  created_at: string
}

export interface UserWhatsAppMessageDetail {
  id: string
  correlation_id: string
  sender_wa_id: string
  message_type: string
  body_text?: string | null
  media_object_key?: string | null
  received_at: string
  processed_at?: string | null
  processing_status: string
  error_code?: string | null
  assistant_reply?: string | null
  raw_payload?: any
  normalized_message?: any
  clarification_status: 'none' | 'awaiting_user' | 'resolved' | 'expired'
  project?: MessageProject | null
  site?: MessageSite | null
  outcome?: MessageOutcome | null
  traces: MessageTrace[]
  providers: MessageProviderExecution[]
}

export interface UserWhatsAppMessageFilters {
  wa_id?: string
  direction?: string
  message_type?: string
  project_id?: string
  site_id?: string
  processing_status?: string
  clarification_status?: string
  has_attachments?: boolean
  search?: string
  date_from?: string
  date_to?: string
  sort?: 'asc' | 'desc'
  limit?: number
  offset?: number
}

export async function fetchUserWhatsAppMessages(
  userId: string,
  filters: UserWhatsAppMessageFilters = {}
): Promise<UserWhatsAppMessageList> {
  const res = await api.get<UserWhatsAppMessageList>(`/users/${userId}/whatsapp/messages`, {
    params: filters,
  })
  return res.data
}

export async function fetchUserWhatsAppMessageDetail(
  userId: string,
  messageId: string
): Promise<UserWhatsAppMessageDetail> {
  const res = await api.get<UserWhatsAppMessageDetail>(`/users/${userId}/whatsapp/messages/${messageId}`)
  return res.data
}

// --- Finance, Expenses, Accounts, and Petty Cash API Integrations ---

export interface RecordExpenseApiPayload {
  project_id: string
  category_id: string
  amount: number
  occurred_date: string
  site_id?: string
  vendor_id?: string
  currency?: string
  description?: string
  source?: string
}

export async function recordExpenseApi(payload: RecordExpenseApiPayload, idempotencyKey: string) {
  const res = await api.post('/expenses', payload, {
    headers: { 'Idempotency-Key': idempotencyKey },
  })
  return res.data
}

export async function fetchExpenseApi(expenseId: string) {
  const res = await api.get(`/expenses/${expenseId}`)
  return res.data
}

export interface CategoryItem {
  id: string
  name: string
  code: string | null
  status: 'active' | 'inactive'
  expense_count: number
  total_amount_spent: number
}

export async function fetchCategoriesApi(): Promise<CategoryItem[]> {
  const res = await api.get('/expenses/categories')
  return res.data
}

export async function createCategoryApi(payload: { name: string; code?: string }): Promise<CategoryItem> {
  const res = await api.post('/expenses/categories', payload)
  return res.data
}

export async function updateCategoryApi(
  categoryId: string,
  payload: { name?: string; code?: string; status?: 'active' | 'inactive' }
): Promise<CategoryItem> {
  const res = await api.patch(`/expenses/categories/${categoryId}`, payload)
  return res.data
}

export interface VendorItem {
  id: string
  name: string
  status: 'active' | 'inactive'
  expense_count: number
  total_amount_paid: number
}

export async function fetchVendorsApi(): Promise<VendorItem[]> {
  const res = await api.get('/finance/vendors')
  return res.data
}

export async function createVendorApi(payload: { name: string }): Promise<VendorItem> {
  const res = await api.post('/finance/vendors', payload)
  return res.data
}

export async function updateVendorApi(
  vendorId: string,
  payload: { name?: string; status?: 'active' | 'inactive' }
): Promise<VendorItem> {
  const res = await api.patch(`/finance/vendors/${vendorId}`, payload)
  return res.data
}

export async function fetchExpensesApi(params?: {
  project_id?: string
  site_id?: string
  category_id?: string
  vendor_id?: string
}) {
  const res = await api.get('/expenses', { params })
  return res.data
}

export async function reverseExpenseApi(expenseId: string) {
  const res = await api.post(`/expenses/${expenseId}/reverse`, {}, {
    headers: {
      'Idempotency-Key': `rev_${Date.now()}_${expenseId}`,
    },
  })
  return res.data
}

export interface ExpenseAttachmentApiItem {
  id: string
  expense_id: string
  attachment_type: string
  created_at: string | null
  url: string
}

export async function fetchExpenseAttachmentsApi(expenseId: string): Promise<ExpenseAttachmentApiItem[]> {
  const res = await api.get(`/expenses/${expenseId}/attachments`)
  return res.data
}

export interface ExpenseAttachmentGalleryApiItem extends ExpenseAttachmentApiItem {
  amount: number
  description: string | null
  occurred_date: string
  project_id: string
  category_name: string | null
  vendor_name: string | null
}

export async function fetchAllExpenseAttachmentsApi(params?: {
  project_id?: string
  site_id?: string
  start_date?: string
  end_date?: string
  limit?: number
  offset?: number
}): Promise<ExpenseAttachmentGalleryApiItem[]> {
  const res = await api.get('/expenses/attachments', { params })
  return res.data
}

export interface CreateAccountApiPayload {
  name: string
  account_type: 'bank' | 'cash' | 'employee_advance' | 'other'
  currency: string
  opening_balance: number
  account_number?: string
  bank_name?: string
  ifsc_code?: string
  custodian_name?: string
  owner_user_id?: string
  project_id?: string
  site_id?: string
}

export async function createAccountApi(payload: CreateAccountApiPayload) {
  const res = await api.post('/finance/accounts', payload)
  return res.data
}

export async function deleteAccountApi(accountId: string) {
  const res = await api.delete(`/finance/accounts/${accountId}`)
  return res.data
}

export async function fetchAccountsApi(params?: { project_id?: string; site_id?: string }) {
  const res = await api.get('/finance/accounts', { params })
  return res.data
}

export interface TransferMoneyApiPayload {
  from_account_id: string
  to_account_id: string
  amount: number
  description?: string
  occurred_date?: string
}

export async function transferMoneyApi(payload: TransferMoneyApiPayload, idempotencyKey: string) {
  const res = await api.post('/finance/transfers', payload, {
    headers: { 'Idempotency-Key': idempotencyKey },
  })
  return res.data
}

export interface RecordVoucherApiPayload {
  cash_box_id: string
  amount: number
  category: string
  vendor_name?: string
  description: string
  date: string
  target_account_id?: string
}

export async function recordVoucherApi(payload: RecordVoucherApiPayload) {
  const key = `vch-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
  if (payload.target_account_id) {
    return transferMoneyApi(
      {
        from_account_id: payload.cash_box_id,
        to_account_id: payload.target_account_id,
        amount: payload.amount,
        description: `${payload.category}: ${payload.description}`,
        occurred_date: payload.date,
      },
      key
    )
  }
  const res = await api.post('/finance/petty-cash/vouchers', payload).catch(() => ({ status: 'simulated' }))
  return res
}

export interface ReplenishFloatApiPayload {
  cash_box_id: string
  source_account_id: string
  amount: number
  notes?: string
}

export async function replenishFloatApi(payload: ReplenishFloatApiPayload) {
  const key = `repl-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
  return transferMoneyApi(
    {
      from_account_id: payload.source_account_id,
      to_account_id: payload.cash_box_id,
      amount: payload.amount,
      description: payload.notes || 'Petty cash float replenishment',
    },
    key
  )
}

export async function fetchAccountTransactionsApi(accountId: string) {
  const res = await api.get(`/finance/accounts/${accountId}/transactions`)
  return res.data
}

export async function fetchVouchersApi(cashBoxId?: string) {
  const res = await api.get('/finance/petty-cash/vouchers', {
    params: cashBoxId ? { cash_box_id: cashBoxId } : undefined,
  })
  return res.data
}

export interface MoneyTransactionItem {
  id: string
  organization_id: string
  transaction_type: string
  amount: number
  occurred_date: string
  created_by: string
  from_account_id: string | null
  from_account_name: string | null
  to_account_id: string | null
  to_account_name: string | null
  source_type: string | null
  source_id: string | null
  description: string | null
  correlation_id: string | null
}

export async function fetchTransactionsApi(params?: {
  transaction_type?: string
  account_id?: string
  start_date?: string
  end_date?: string
  limit?: number
}): Promise<MoneyTransactionItem[]> {
  const res = await api.get('/finance/transactions', { params })
  return res.data
}

export interface CategoryBreakdownItem {
  id: string
  name: string
  amount: number
}

export interface MonthlyTrendItem {
  month: string
  amount: number
  count: number
}

export interface TopVendorItem {
  id: string
  name: string
  total_spent: number
  unpaid_amount: number
}

export interface PettyCashSummaryItem {
  id: string
  name: string
  custodian_name: string
  current_balance: number
  opening_balance: number
}

export interface FinanceHealthAlerts {
  low_float_count: number
  unpaid_invoice_count: number
  total_unpaid_amount: number
}

export interface FinanceSummaryItem {
  total_liquidity: number
  total_expenses: number
  unpaid_expenses: number
  active_accounts_count: number
  active_vendors_count: number
  active_categories_count: number
  category_breakdown: CategoryBreakdownItem[]
  monthly_trend: MonthlyTrendItem[]
  top_vendors: TopVendorItem[]
  petty_cash_accounts: PettyCashSummaryItem[]
  health_alerts: FinanceHealthAlerts
}

export async function fetchFinanceSummaryApi(): Promise<FinanceSummaryItem> {
  const res = await api.get('/finance/summary')
  return res.data
}

export interface FinanceSettingsItem {
  base_currency: string
  currency_symbol: string
  fiscal_year_start: string
  low_float_threshold: number
  auto_approval_limit: number
  require_receipt_above: number
  duplicate_window_hours: number
  default_tax_rate: number
  enabled_payment_methods: string[]
  low_balance_warning_enabled?: boolean
  transfer_receipt_enabled?: boolean
  expense_card_enabled?: boolean
  weekly_digest_enabled?: boolean
  weekly_digest_schedule?: string
}

export async function fetchFinanceSettingsApi(): Promise<FinanceSettingsItem> {
  const res = await api.get('/finance/settings')
  return res.data
}

export async function updateFinanceSettingsApi(
  payload: Partial<FinanceSettingsItem>
): Promise<FinanceSettingsItem> {
  const res = await api.patch('/finance/settings', payload)
  return res.data
}

export interface FinanceReportRow {
  id: string
  code: string | null
  title: string
  category: string | null
  account_name: string | null
  amount: number
  percentage: number | null
  status: string | null
  notes: string | null
}

export interface FinanceReportStatementItem {
  report_type: string
  title: string
  subtitle: string
  generated_at: string
  total_inflows: number
  total_outflows: number
  net_margin: number
  rows: FinanceReportRow[]
}

export async function fetchFinanceReportApi(params?: {
  report_type?: string
}): Promise<FinanceReportStatementItem> {
  const res = await api.get('/finance/reports/statement', { params })
  return res.data
}



