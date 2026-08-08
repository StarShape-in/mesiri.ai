/**
 * Operator Home screen. Composes the dashboard feature's hooks + components
 * only — no direct API calls and no business logic live here.
 *
 * The bottom tab bar isn't rendered by this screen: it's mounted once, above
 * the route stack, in src/app/_layout.tsx (`<OperatorBottomNav />`), so every
 * operator screen shares one persistent nav instead of remounting it.
 */
import React, { useState } from 'react';
import { RefreshControl, ScrollView, View } from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useAuth } from '@/lib/auth-context';

import {
  useActiveTrips, useCurrentUser, useDashboardRefresh,
  useDashboardSummary, useDelayedDeliveries, useNotifications,
} from '../hooks';
import {
  ActiveVehiclesSection, AppHeader, ContextSelector, DashboardMetricCard,
  DocumentExpirySection, ScannerButton, SearchBar,
} from '../components';
import { ErrorState, SkeletonMetricCard } from '@/shared/components';

export default function DashboardHomeScreen() {
  const router = useRouter();
  const { role } = useAuth();
  const { refreshing, refresh } = useDashboardRefresh();

  const [search, setSearch] = useState('');

  const currentUser = useCurrentUser();
  const notifications = useNotifications();
  const summary = useDashboardSummary();
  const activeTrips = useActiveTrips();
  const delayedDeliveries = useDelayedDeliveries();

  const firstName = (currentUser.data?.name ?? 'Operator').split(' ')[0];
  const unreadCount = notifications.data?.filter((n) => !n.is_read).length ?? 0;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: '#FFFFFF' }} edges={['top']}>
      <ScrollView
        contentContainerStyle={{ padding: 16, paddingBottom: 96, gap: 20 }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor="#E8450F" />}
      >
        {/* 1. AppHeader */}
        <AppHeader
          logoSource={require('@/assets/images/mercon-logo.png')}
          greeting="Welcome back,"
          userName={firstName}
          unreadNotifications={unreadCount}
          onNotificationPress={() => router.push('/notifications')}
        />

        {/* 2. Context Selector Row */}
        <ContextSelector role={role ?? 'Operator'} />

        {/* 3. Search Row */}
        <View className="flex-row items-center gap-2">
          <SearchBar value={search} onChangeText={setSearch} onSubmit={() => router.push('/operator/trips')} />
          <ScannerButton />
        </View>

        {/* 4. Dashboard Metrics */}
        {summary.isLoading || activeTrips.isLoading || delayedDeliveries.isLoading ? (
          <View className="flex-row gap-3">
            <SkeletonMetricCard />
            <SkeletonMetricCard />
          </View>
        ) : summary.isError ? (
          <ErrorState message="Couldn't load dashboard metrics." onRetry={() => summary.refetch()} />
        ) : (
          <View className="flex-row gap-3">
            <DashboardMetricCard
              title="Active Trips"
              value={activeTrips.data?.length ?? 0}
              image={require('@/assets/images/mobile-truck.png')}
              onPress={() => router.push('/operator/trips')}
            />
            <DashboardMetricCard
              title="Delayed Deliveries"
              value={delayedDeliveries.data?.length ?? 0}
              onPress={() => router.push('/operator/trips')}
            />
          </View>
        )}

        {/* 5-6. Active Vehicles — header, carousel, pagination */}
        <ActiveVehiclesSection
          onViewAll={() => router.push('/operator/vehicles')}
          onVehiclePress={(v) => router.push({ pathname: '/operator/trip-details', params: { id: v.tripId } })}
        />

        {/* 7. Document Expiry — replaces Fleet Utilization */}
        <DocumentExpirySection
          onViewAll={() => router.push('/operator/vehicle-renewals')}
        />
      </ScrollView>
    </SafeAreaView>
  );
}
