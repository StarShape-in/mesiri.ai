import React, { useCallback, useState } from 'react';
import { ActivityIndicator, FlatList, RefreshControl, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Building2 } from 'lucide-react-native';
import { Colors } from '@/theme/tokens';
import { EmptyState, ErrorState } from '@/shared/components';
import {
  CustomerCard,
  CustomerListHeader,
  CustomersHeader,
  CustomerStatsSection,
  SkeletonCustomerCard,
} from '../components';
import {
  useCustomerActions,
  useCustomerFilters,
  useCustomerPermissions,
  useCustomers,
  useCustomerSearch,
  useCustomerSorting,
  useCustomerStats,
} from '../hooks';
import type { CustomerListItem } from '../types';

const SCREEN_PADDING = 16;
const CANVAS = '#F7F7F9';

/**
 * Customers — the operations hub for customer companies.
 *
 * Presentation only: every request, transform and side effect lives in the
 * feature's hooks. Route is /operator/customers, reached from More → Customers.
 */
export default function CustomersScreen() {
  const router = useRouter();

  const [searchVisible, setSearchVisible] = useState(false);
  const [filtersVisible, setFiltersVisible] = useState(false);

  const { query, setQuery, debouncedQuery } = useCustomerSearch();
  const { status, setStatus } = useCustomerFilters();
  const { sort, setSort } = useCustomerSorting();

  const {
    customers, total, loading, error, refresh, isRefreshing,
    fetchNextPage, hasNextPage, isFetchingNextPage,
  } = useCustomers({ search: debouncedQuery, status, sort });

  const { stats, loading: statsLoading } = useCustomerStats();
  const permissions = useCustomerPermissions();
  const { toggleActive, deleteCustomer } = useCustomerActions();

  const openEdit = useCallback(
    (customer: CustomerListItem) =>
      router.push({ pathname: '/operator/customer-edit', params: { id: customer.id } }),
    [router],
  );

  // No customer-details screen exists yet — customer-edit is the real screen
  // that shows the full record, so "View Details" opens that rather than a
  // dead route.
  const openDetails = openEdit;

  const openCreate = useCallback(
    () => router.push('/operator/customer-edit'),
    [router],
  );

  const createTrip = useCallback(
    (customer: CustomerListItem) =>
      router.push({ pathname: '/operator/create-trip', params: { customerId: customer.id } }),
    [router],
  );

  const renderItem = useCallback(
    ({ item }: { item: CustomerListItem }) => (
      <CustomerCard
        customer={item}
        permissions={permissions}
        onViewDetails={openDetails}
        onCreateTrip={createTrip}
        onEdit={openEdit}
        onToggleActive={toggleActive}
        onDelete={deleteCustomer}
      />
    ),
    [permissions, openDetails, createTrip, openEdit, toggleActive, deleteCustomer],
  );

  return (
    <SafeAreaView edges={['top']} className="flex-1" style={{ backgroundColor: CANVAS }}>
      <CustomersHeader
        searchVisible={searchVisible}
        onToggleSearch={() => setSearchVisible((v) => !v)}
        query={query}
        onQueryChange={setQuery}
        filtersVisible={filtersVisible}
        onToggleFilters={() => setFiltersVisible((v) => !v)}
        status={status}
        onStatusChange={setStatus}
        canCreate={permissions.canCreate}
        onAddCustomer={openCreate}
      />

      {error ? (
        <ErrorState message={error} onRetry={refresh} className="flex-1" />
      ) : (
        <FlatList
          data={customers}
          keyExtractor={(item) => item.id}
          renderItem={renderItem}
          contentContainerStyle={{
            paddingHorizontal: SCREEN_PADDING,
            paddingTop: 16,
            paddingBottom: 100,
          }}
          ItemSeparatorComponent={() => <View style={{ height: 14 }} />}
          refreshControl={
            <RefreshControl refreshing={isRefreshing} onRefresh={refresh} tintColor={Colors.accent} />
          }
          onEndReachedThreshold={0.4}
          onEndReached={() => { if (hasNextPage && !isFetchingNextPage) fetchNextPage(); }}
          ListHeaderComponent={
            <View style={{ gap: 20 }} className="pb-5">
              <CustomerStatsSection stats={stats} loading={statsLoading} inset={SCREEN_PADDING} />
              <CustomerListHeader total={total} sort={sort} onSortChange={setSort} />
            </View>
          }
          ListEmptyComponent={
            loading ? (
              <View style={{ gap: 14 }}>
                <SkeletonCustomerCard />
                <SkeletonCustomerCard />
                <SkeletonCustomerCard />
              </View>
            ) : (
              <EmptyState
                Icon={Building2}
                title="No customers found"
                subtitle={
                  debouncedQuery || status !== 'all'
                    ? 'Try a different search or filter.'
                    : 'Add your first customer to get started.'
                }
                className="mt-8"
              />
            )
          }
          ListFooterComponent={
            isFetchingNextPage ? <ActivityIndicator color={Colors.accent} style={{ marginTop: 16 }} /> : null
          }
        />
      )}
    </SafeAreaView>
  );
}
