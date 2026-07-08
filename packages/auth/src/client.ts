import axios from 'axios';
import * as SecureStore from 'expo-secure-store';

const TOKEN_KEY = 'mesiri_access_token';

// Create a configured Axios instance
export const api = axios.create({
  baseURL: process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000',
  timeout: 15000,
});

// Request interceptor to attach the JWT token to every request and log the request
api.interceptors.request.use(
  async (config) => {
    const token = await SecureStore.getItemAsync(TOKEN_KEY);
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    console.log(`[API REQUEST] ${config.method?.toUpperCase()} ${config.baseURL}${config.url}`);
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor to log errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      console.error(`[API ERROR] ${error.config?.method?.toUpperCase()} ${error.config?.url} - Status: ${error.response.status}`);
      console.error('Response data:', error.response.data);
    } else {
      console.error(`[API ERROR] Network/Unknown:`, error.message);
    }
    return Promise.reject(error);
  }
);

export async function login(email: string, password: string) {
// Bypass removed so we only use real JWTs

  const response = await api.post('/auth/login', { email, password });
  const { access_token } = response.data;
  
  if (access_token) {
    await SecureStore.setItemAsync(TOKEN_KEY, access_token);
  }
  return response.data;
}

export async function logout() {
  await SecureStore.deleteItemAsync(TOKEN_KEY);
}

export async function getToken() {
  return await SecureStore.getItemAsync(TOKEN_KEY);
}
