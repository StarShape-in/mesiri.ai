import { Stack, useRouter, useSegments } from 'expo-router';
import { useEffect, useState, createContext, useContext } from 'react';
import { getToken } from '@mesiri/auth';
import { View, ActivityIndicator } from 'react-native';
import { ThemeProvider, useTheme } from '../src/theme';

export type Capability = 'projects.view' | 'projects.create' | 'gallery.view' | 'dprs.view' | 'expenses.view';

export type User = {
  id: string;
  name: string;
  role: 'Admin' | 'Project Manager' | 'Finance / Accountant' | 'Site Engineer';
  company: string;
  capabilities: Capability[];
};

type AuthContextType = {
  user: User | null;
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
  return (
    <ThemeProvider>
      <AppContent />
    </ThemeProvider>
  );
}

function AppContent() {
  const [isLoading, setIsLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const segments = useSegments();
  const router = useRouter();
  const { theme } = useTheme();

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
    } else if (isAuthenticated && segments[0] === 'login') {
      // Redirect to the unified app surface if authenticated
      router.replace('/(app)');
    }
  }, [isAuthenticated, segments, isLoading]);

  if (isLoading) {
    return (
      <View style={{ flex: 1, backgroundColor: theme.colors.backgroundApp, justifyContent: 'center', alignItems: 'center' }}>
        <ActivityIndicator size="large" color={theme.colors.actionPrimary} />
      </View>
    );
  }

  return (
    <AuthContext.Provider
      value={{
        user: isAuthenticated ? {
          id: 'u1',
          name: 'Ilan Admin',
          role: 'Admin',
          company: 'Skyline Build Co.',
          capabilities: ['projects.view', 'projects.create', 'gallery.view', 'dprs.view', 'expenses.view']
        } : null,
        signIn: () => setIsAuthenticated(true),
        signOut: () => setIsAuthenticated(false),
        isLoading,
      }}>
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: theme.colors.backgroundApp } }}>
        <Stack.Screen name="login" options={{ animation: 'fade' }} />
        <Stack.Screen name="(app)" options={{ animation: 'fade' }} />
      </Stack>
    </AuthContext.Provider>
  );
}
