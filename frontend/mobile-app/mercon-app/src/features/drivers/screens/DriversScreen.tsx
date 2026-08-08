/**
 * Operator Drivers screen. Composes the drivers feature's hooks + components
 * only — no direct API calls and no business logic live here.
 *
 * The bottom tab bar isn't rendered by this screen: it's mounted once, above
 * the route stack, in src/app/_layout.tsx (`<OperatorBottomNav />`).
 */
import React, { useState } from 'react';
import { ActivityIndicator, FlatList, Linking, RefreshControl, View } from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Users } from 'lucide-react-native';

import { SearchBar } from '@/features/dashboard/components';
import { EmptyState, ErrorState } from '@/shared/components';

import {
  DriverCard, DriversHeader, DriversListHeader, DriverStatsSection, FilterBottomSheet, SkeletonDriverCard,
} from '../components';
import { useDriverFilters, useDriverSearch, useDriverSorting, useDrivers } from '../hooks';
import type { DriverListItem } from '../types';

export default function DriversScreen() {
  const router = useRouter();
  const [searchVisible, setSearchVisible] = useState(false);
  const [filterVisible, setFilterVisible] = useState(false);

  const { query, debouncedQuery, setQuery } = useDriverSearch();
  const { status, setStatus } = useDriverFilters();
  const { sort, setSort } = useDriverSorting();

  const {
    drivers, total, loading, error, refresh, isRefreshing, fetchNextPage, hasNextPage, isFetchingNextPage,
  } = useDrivers({ search: debouncedQuery, status, sort });

  const openDriver = (driver: DriverListItem) => {
    router.push({ pathname: '/operator/driver-details', params: { id: driver.id } });
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: '#FFFFFF' }} edges={['top']}>
      <DriversHeader
        onSearchPress={() => setSearchVisible((v) => !v)}
        onFilterPress={() => setFilterVisible(true)}
        filterActive={status !== null}
      />

      {searchVisible && (
        <View className="px-4 pb-3">
          <SearchBar value={query} onChangeText={setQuery} placeholder="Search drivers by name…" />
        </View>
      )}

      {error ? (
        <ErrorState message={error} onRetry={() => refresh()} className="flex-1" />
      ) : (
        <FlatList
          data={drivers}
          keyExtractor={(item) => item.id}
          contentContainerStyle={{ paddingHorizontal: 16, paddingTop: 4, paddingBottom: 100 }}
          ItemSeparatorComponent={() => <View style={{ height: 14 }} />}
          refreshControl={<RefreshControl refreshing={isRefreshing} onRefresh={refresh} tintColor="#F24822" />}
          onEndReachedThreshold={0.4}
          onEndReached={() => { if (hasNextPage) fetchNextPage(); }}
          ListHeaderComponent={
            <View className="gap-6 pb-5">
              <DriverStatsSection />
              <DriversListHeader total={total} sort={sort} onSortChange={setSort} />
            </View>
          }
          renderItem={({ item }) => (
            <DriverCard
              driver={item}
              onView={openDriver}
              onCall={(d) => d.phone && Linking.openURL(`tel:${d.phone}`).catch(() => {})}
              onTrack={(d) => d.activeTrip && router.push({ pathname: '/operator/trip-details', params: { id: d.activeTrip.id } })}
            />
          )}
          ListEmptyComponent={
            loading ? (
              <View className="gap-3.5">
                <SkeletonDriverCard />
                <SkeletonDriverCard />
                <SkeletonDriverCard />
              </View>
            ) : (
              <EmptyState title="No drivers found" subtitle="Try a different search or filter." Icon={Users} className="mt-8" />
            )
          }
          ListFooterComponent={isFetchingNextPage ? <ActivityIndicator color="#F24822" style={{ marginTop: 16 }} /> : null}
        />
      )}

      <FilterBottomSheet
        visible={filterVisible}
        value={status}
        onChange={setStatus}
        onClose={() => setFilterVisible(false)}
      />
    </SafeAreaView>
  );
}
