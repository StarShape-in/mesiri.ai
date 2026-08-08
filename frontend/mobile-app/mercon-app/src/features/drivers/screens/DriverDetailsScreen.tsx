import React, { useCallback } from 'react';
import { RefreshControl, ScrollView, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { MessageSquare, Phone, UserX } from 'lucide-react-native';
import { Colors } from '@/theme/tokens';
import { EmptyState, ErrorState } from '@/shared/components';
import {
  AssignedVehicleCard,
  ContactInformationCard,
  CurrentAssignmentCard,
  DocumentsSection,
  DriverHeader,
  DriverProfileCard,
  PerformanceSummary,
  PrimaryActionButton,
  PrimaryActions,
  SCREEN_PADDING,
  Section,
  SectionCard,
  SecondaryActionButton,
  SkeletonDriverDetails,
} from '../components';
import { useDriver, useDriverActions } from '../hooks';

/** Page background — a hair off white so the white cards read as raised. */
const CANVAS = '#F7F7F9';

/**
 * Driver Details — the operator's hub for one driver.
 *
 * Presentation only: every request, transform and side effect lives in
 * `useDriver` / `useDriverActions`. Route is /operator/driver-details?id=.
 */
export default function DriverDetailsScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();

  const {
    driver,
    vehicle,
    documents,
    documentsNeedingAttention,
    documentsLoading,
    documentsError,
    performance,
    assignment,
    loading,
    refreshing,
    error,
    notFound,
    refresh,
  } = useDriver(id);

  const { callDriver, messageDriver, canContact } = useDriverActions(id, driver?.phone ?? null);

  const handleBack = useCallback(() => {
    if (router.canGoBack()) router.back();
    else router.replace('/operator/drivers');
  }, [router]);

  const handleEdit = useCallback(
    () => router.push({ pathname: '/operator/driver-edit', params: { id } }),
    [router, id],
  );

  // There is no vehicle-details route in the app yet; vehicle-edit is the real
  // destination that shows this vehicle's record.
  const handleViewVehicle = useCallback(() => {
    if (vehicle) router.push({ pathname: '/operator/vehicle-edit', params: { id: vehicle.id } });
  }, [router, vehicle]);

  const handleTrackTrip = useCallback(() => {
    if (assignment) router.push({ pathname: '/operator/trip-details', params: { id: assignment.tripId } });
  }, [router, assignment]);

  const handleViewAllDocuments = useCallback(() => router.push('/documents'), [router]);

  const renderBody = () => {
    if (loading) return <SkeletonDriverDetails />;

    if (notFound) {
      return (
        <SectionCard>
          <EmptyState Icon={UserX} title="Driver not found" subtitle="This driver may have been removed." />
        </SectionCard>
      );
    }

    if (error || !driver) {
      return (
        <SectionCard>
          <ErrorState message={error ?? 'Could not load this driver.'} onRetry={refresh} />
        </SectionCard>
      );
    }

    return (
      <>
        <DriverProfileCard driver={driver} performance={performance} />

        {/* Hidden entirely when the driver is not currently on a trip — a
            driver has no standing vehicle assignment in the schema. */}
        {vehicle && <AssignedVehicleCard vehicle={vehicle} onViewVehicle={handleViewVehicle} />}

        <ContactInformationCard driver={driver} />

        <DocumentsSection
          documents={documents}
          needsAttention={documentsNeedingAttention}
          loading={documentsLoading}
          error={documentsError}
          onRetry={refresh}
          onViewAll={handleViewAllDocuments}
        />

        {assignment ? (
          <CurrentAssignmentCard assignment={assignment} onTrackTrip={handleTrackTrip} />
        ) : (
          <Section title="Current Assignment">
            <SectionCard>
              <EmptyState title="No Active Assignment" subtitle="This driver is not on a trip right now." />
            </SectionCard>
          </Section>
        )}

        <PerformanceSummary performance={performance} />

        <View className="pt-1">
          <PrimaryActions>
            <PrimaryActionButton label="Call Driver" Icon={Phone} onPress={callDriver} disabled={!canContact} />
            <SecondaryActionButton label="Message" Icon={MessageSquare} onPress={messageDriver} disabled={!canContact} />
          </PrimaryActions>
        </View>
      </>
    );
  };

  return (
    <SafeAreaView edges={['top']} className="flex-1" style={{ backgroundColor: CANVAS }}>
      <DriverHeader onBack={handleBack} onEdit={driver ? handleEdit : undefined} />
      <ScrollView
        className="flex-1"
        contentContainerStyle={{
          padding: SCREEN_PADDING,
          paddingTop: 8,
          paddingBottom: 40,
          gap: 20,
        }}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor={Colors.accent} />
        }
      >
        {renderBody()}
      </ScrollView>
    </SafeAreaView>
  );
}
