import axios from 'axios';
import * as SecureStore from 'expo-secure-store';

const TOKEN_KEY = 'mesiri_access_token';

// Create a configured Axios instance
export const api = axios.create({
  baseURL: process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000',
  timeout: 10000,
});

// Request interceptor to attach the JWT token to every request
api.interceptors.request.use(
  async (config) => {
    const token = await SecureStore.getItemAsync(TOKEN_KEY);
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

export async function login(email: string, password: string) {
  // Hardcoded bypass for testing the UI
  if (email === 'ilan@erp.com' && password === 'ilan1234') {
    const mockToken = "mock_jwt_token_for_ilan";
    await SecureStore.setItemAsync(TOKEN_KEY, mockToken);
    return { access_token: mockToken, token_type: 'bearer' };
  }

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
