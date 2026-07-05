import { Stack, useRouter, useSegments } from 'expo-router';
import { useEffect, useState, createContext, useContext } from 'react';
import { getToken } from '@mesiri/auth';
import { View, ActivityIndicator } from 'react-native';

type AuthContextType = {
  signIn: () => void;
  signOut: () => void;
  isLoading: boolean;
};

const AuthContext = createContext<AuthContextType | null>(null);

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within an AuthProvider');
  return context;
}

export default function RootLayout() {
  const [isLoading, setIsLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    // Check if user has a token on boot
    async function checkAuth() {
      try {
        const token = await getToken();
        setIsAuthenticated(!!token);
      } catch (e) {
        setIsAuthenticated(false);
      } finally {
        setIsLoading(false);
      }
    }
    checkAuth();
  }, []);

  useEffect(() => {
    if (isLoading) return;

    const inAuthGroup = segments[0] === '(app)';
    
    if (!isAuthenticated && inAuthGroup) {
      // Redirect to login if not authenticated but trying to access protected area
      router.replace('/login');
    } else if (isAuthenticated && !inAuthGroup) {
      // Redirect to app if authenticated but on login screen
      router.replace('/(app)');
    }
  }, [isAuthenticated, segments, isLoading]);

  if (isLoading) {
    return (
      <View style={{ flex: 1, backgroundColor: '#FAFAFB', justifyContent: 'center', alignItems: 'center' }}>
        <ActivityIndicator size="large" color="#7ED957" />
      </View>
    );
  }

  return (
    <AuthContext.Provider
      value={{
        signIn: () => setIsAuthenticated(true),
        signOut: () => setIsAuthenticated(false),
        isLoading,
      }}>
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: '#FAFAFB' } }}>
        <Stack.Screen name="login" options={{ animation: 'fade' }} />
        <Stack.Screen name="(app)" options={{ animation: 'fade' }} />
      </Stack>
    </AuthContext.Provider>
  );
}
