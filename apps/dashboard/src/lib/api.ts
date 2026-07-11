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
