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


