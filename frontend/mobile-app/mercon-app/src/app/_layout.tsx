import '../global.css';

import { Stack, usePathname } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { useEffect } from 'react';
import { View, StyleSheet } from 'react-native';
import { QueryClientProvider } from '@tanstack/react-query';

import { AuthProvider, useAuth } from '@/lib/auth-context';
import { queryClient } from '@/lib/query-client';
import { DriverBottomNav } from '@/navigation/DriverBottomNav';
import { OperatorBottomNav } from '@/navigation/OperatorBottomNav';

SplashScreen.preventAutoHideAsync();

const TAB_ROUTES = [
  '/', '/trips', '/profile', '/notifications', '/documents', '/vehicle', '/settings',
  '/operator/trips', '/operator/drivers', '/operator/vehicles', '/operator/invoices',
  '/operator/more', '/operator/customers',
];

function RootNavigator() {
  const { isLoggedIn, isLoading, role } = useAuth();
  const pathname = usePathname();

  // Keep the native splash visible until the session is restored,
  // so the user never sees a flash of the wrong screen.
  useEffect(() => {
    if (!isLoading) SplashScreen.hideAsync();
  }, [isLoading]);

  if (isLoading) return null;

  const showBottomNav = isLoggedIn && TAB_ROUTES.some((r) => pathname === r || pathname.startsWith(r + '/'));

  return (
    <View style={styles.container}>
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: '#F3F4F6' } }}>
        <Stack.Protected guard={isLoggedIn}>
          {/* Tab / hub screens switch instantly without animations */}
          <Stack.Screen name="index" options={{ animation: 'none' }} />
          <Stack.Screen name="trips" options={{ animation: 'none' }} />
          <Stack.Screen name="profile" options={{ animation: 'none' }} />
          <Stack.Screen name="notifications" options={{ animation: 'none' }} />
          <Stack.Screen name="documents" options={{ animation: 'none' }} />
          <Stack.Screen name="vehicle" options={{ animation: 'none' }} />
          <Stack.Screen name="settings" options={{ animation: 'none' }} />
          {/* Trip flow keeps the sequential push animation */}
          <Stack.Screen name="trip/pickup" />
          <Stack.Screen name="trip/navigate" />
          <Stack.Screen name="trip/delivery" />
          <Stack.Screen name="trip/completed" />
          {/* Operator screens */}
          <Stack.Screen name="operator/trips" options={{ animation: 'none' }} />
          <Stack.Screen name="operator/drivers" options={{ animation: 'none' }} />
          <Stack.Screen name="operator/vehicles" options={{ animation: 'none' }} />
          <Stack.Screen name="operator/invoices" options={{ animation: 'none' }} />
          <Stack.Screen name="operator/more" options={{ animation: 'none' }} />
          <Stack.Screen name="operator/customers" options={{ animation: 'none' }} />
          <Stack.Screen name="operator/trip-details" />
          <Stack.Screen name="operator/create-trip" />
          <Stack.Screen name="operator/vehicle-renewals" />
          <Stack.Screen name="operator/driver-edit" />
          <Stack.Screen name="operator/vehicle-edit" />
          <Stack.Screen name="operator/customer-edit" />
        </Stack.Protected>

        <Stack.Protected guard={!isLoggedIn}>
          <Stack.Screen name="login" />
        </Stack.Protected>
      </Stack>

      {showBottomNav && (
        <View style={styles.floatingNavOverlay} pointerEvents="box-none">
          {role === 'Operator' || role === 'Admin' ? <OperatorBottomNav /> : <DriverBottomNav />}
        </View>
      )}
    </View>
  );
}

export default function RootLayout() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <RootNavigator />
      </AuthProvider>
    </QueryClientProvider>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  floatingNavOverlay: {
    position: 'absolute',
    bottom: 16,
    left: 0,
    right: 0,
    zIndex: 9999,
  },
});
