import { Platform } from 'react-native';

const isWeb = Platform.OS === 'web' || typeof window !== 'undefined';

let NativeSecureStore: any = null;
if (Platform.OS !== 'web') {
  try {
    NativeSecureStore = require('expo-secure-store');
  } catch (e) {
    // Native module not loaded
  }
}

export const safeSecureStore = {
  getItemAsync: async (key: string): Promise<string | null> => {
    if (isWeb || !NativeSecureStore) {
      if (typeof window !== 'undefined' && window.localStorage) {
        return window.localStorage.getItem(key);
      }
      return null;
    }
    try {
      return await NativeSecureStore.getItemAsync(key);
    } catch (e) {
      if (typeof window !== 'undefined' && window.localStorage) {
        return window.localStorage.getItem(key);
      }
      return null;
    }
  },
  setItemAsync: async (key: string, value: string): Promise<void> => {
    if (isWeb || !NativeSecureStore) {
      if (typeof window !== 'undefined' && window.localStorage) {
        window.localStorage.setItem(key, value);
      }
      return;
    }
    try {
      await NativeSecureStore.setItemAsync(key, value);
    } catch (e) {
      if (typeof window !== 'undefined' && window.localStorage) {
        window.localStorage.setItem(key, value);
      }
    }
  },
  deleteItemAsync: async (key: string): Promise<void> => {
    if (isWeb || !NativeSecureStore) {
      if (typeof window !== 'undefined' && window.localStorage) {
        window.localStorage.removeItem(key);
      }
      return;
    }
    try {
      await NativeSecureStore.deleteItemAsync(key);
    } catch (e) {
      if (typeof window !== 'undefined' && window.localStorage) {
        window.localStorage.removeItem(key);
      }
    }
  },
};
