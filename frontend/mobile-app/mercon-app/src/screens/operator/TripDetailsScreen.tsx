import React, { useState } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity, Modal, FlatList,
  StyleSheet, SafeAreaView, StatusBar, Linking, Alert, ActivityIndicator,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { ArrowLeft, ArrowRight, Check, Phone, Truck, MapPin, X } from 'lucide-react-native';
import { Colors, Spacing, Radius, Typography } from '../../theme/tokens';
import { StatusBadge, Avatar, Card, Button } from '../../components';
import { getApiErrorMessage } from '../../lib/api';
import {
  operatorService, useOperatorTripById, type OperatorTripDetail, type OperatorDriver,
} from '../../lib/operator';
import { statusLabel, type TripStatus } from '../../lib/trips';

const NEXT_STEP: Partial<Record<TripStatus, { label: string; action: (id: string) => Promise<unknown>; confirm?: string }>> = {
  Dispatched: { label: 'Mark Arrived at Pickup', action: (id) => operatorService.pickupArrive(id) },
  AtPickup: { label: 'Verify Pickup & Depart', action: (id) => operatorService.updateTripStatus(id, 'InTransit') },
  InTransit: { label: 'Arrived at Delivery', action: (id) => operatorService.updateTripStatus(id, 'AtDelivery') },
  AtDelivery: {
    label: 'Confirm Delivery',
    action: (id) => operatorService.updateTripStatus(id, 'Completed'),
    confirm: 'This confirms the delivery, completes the trip, and generates the invoice. Continue?',
  },
};

const ACTIVE_STATUSES: TripStatus[] = ['Dispatched', 'AtPickup', 'InTransit', 'AtDelivery'];

const STATUS_STEPS: { status: TripStatus; label: string }[] = [
  { status: 'Draft', label: 'Trip Created' },
  { status: 'Dispatched', label: 'Driver Assigned' },
  { status: 'AtPickup', label: 'Pickup Verified' },
  { status: 'InTransit', label: 'In Transit' },
  { status: 'AtDelivery', label: 'Destination Reached' },
  { status: 'Completed', label: 'Delivery Confirmed' },
];

function stepIndex(status: TripStatus): number {
  const i = STATUS_STEPS.findIndex((s) => s.status === status);
  return i === -1 ? STATUS_STEPS.length - 1 : i; // Invoiced/Cancelled treated as terminal
}

function formatDateTime(iso?: string | null): string {
  if (!iso) return 'Pending';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return 'Pending';
  return d.toLocaleString(undefined, { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
}

function buildTimeline(trip: OperatorTripDetail) {
  const currentIndex = trip.status === 'Cancelled' ? -1 : stepIndex(trip.status);
  const pickupStop = trip.stops.find((s) => s.stop_type === 'Pickup');
  const dropoffStop = trip.stops.find((s) => s.stop_type === 'Dropoff');

  const timeFor = (i: number): string | null => {
    switch (STATUS_STEPS[i].status) {
      case 'Draft': return trip.createdAt;
      case 'Dispatched': return trip.planned_start ?? null;
      case 'AtPickup': return pickupStop?.actual_arrival ?? null;
      case 'InTransit': return trip.actual_start ?? null;
      case 'AtDelivery': return dropoffStop?.actual_arrival ?? null;
      case 'Completed': return trip.actual_end ?? null;
      default: return null;
    }
  };

  return STATUS_STEPS.map((step, i) => ({
    id: step.status,
    label: step.label,
    time: i <= currentIndex ? formatDateTime(timeFor(i)) : 'Pending',
    done: i < currentIndex || (i === currentIndex && trip.status === 'Completed'),
    active: i === currentIndex && trip.status !== 'Completed',
  }));
}

const driverName = (trip: OperatorTripDetail) =>
  trip.driver ? `${trip.driver.first_name} ${trip.driver.last_name}` : 'Unassigned';

const TripDetailsScreen = () => {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { trip, loading, error, refetch } = useOperatorTripById(id);
  const [advancing, setAdvancing] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [showReplaceDriver, setShowReplaceDriver] = useState(false);
  const [availableDrivers, setAvailableDrivers] = useState<OperatorDriver[]>([]);
  const [loadingDrivers, setLoadingDrivers] = useState(false);
  const [replacingId, setReplacingId] = useState<string | null>(null);

  const handleAdvance = () => {
    if (!trip || !id) return;
    const next = NEXT_STEP[trip.status];
    if (!next) return;
    const run = async () => {
      setAdvancing(true);
      try {
        await next.action(id);
        await refetch();
      } catch (e) {
        Alert.alert('Could not update trip', getApiErrorMessage(e));
      } finally {
        setAdvancing(false);
      }
    };
    if (next.confirm) {
      Alert.alert('Confirm', next.confirm, [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Confirm', onPress: run },
      ]);
    } else {
      run();
    }
  };

  const handleCancelTrip = () => {
    if (!id) return;
    Alert.alert('Cancel Trip', 'This releases the driver and vehicle and cannot be undone. Cancel this trip?', [
      { text: 'No', style: 'cancel' },
      {
        text: 'Cancel Trip',
        style: 'destructive',
        onPress: async () => {
          setCancelling(true);
          try {
            await operatorService.updateTripStatus(id, 'Cancelled');
            await refetch();
          } catch (e) {
            Alert.alert('Could not cancel trip', getApiErrorMessage(e));
          } finally {
            setCancelling(false);
          }
        },
      },
    ]);
  };

  const openReplaceDriver = async () => {
    setShowReplaceDriver(true);
    setLoadingDrivers(true);
    try {
      const drivers = await operatorService.availableDrivers();
      setAvailableDrivers(drivers);
    } catch (e) {
      Alert.alert('Could not load drivers', getApiErrorMessage(e));
    } finally {
      setLoadingDrivers(false);
    }
  };

  const handleReplaceDriver = (newDriverId: string) => {
    if (!id) return;
    setReplacingId(newDriverId);
    operatorService.replaceDriver(id, newDriverId)
      .then(async () => {
        setShowReplaceDriver(false);
        await refetch();
      })
      .catch((e) => Alert.alert('Could not replace driver', getApiErrorMessage(e)))
      .finally(() => setReplacingId(null));
  };

  if (loading && !trip) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: Colors.gray100, justifyContent: 'center' }}>
        <ActivityIndicator color={Colors.primary} />
      </SafeAreaView>
    );
  }

  if (!trip) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: Colors.gray100, justifyContent: 'center', alignItems: 'center' }}>
        <Text style={styles.emptyText}>{error ?? 'Trip not found'}</Text>
        <TouchableOpacity onPress={() => router.back()} style={{ marginTop: Spacing.lg }}>
          <Text style={{ color: Colors.primary, fontWeight: '700' }}>Go Back</Text>
        </TouchableOpacity>
      </SafeAreaView>
    );
  }

  const pickupStop = trip.stops.find((s) => s.stop_type === 'Pickup');
  const dropoffStop = trip.stops.find((s) => s.stop_type === 'Dropoff');
  const timeline = buildTimeline(trip);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.gray100 }}>
      <StatusBar barStyle="light-content" backgroundColor={Colors.darkCard} />
      <ScrollView contentContainerStyle={styles.scroll}>
        {/* Dark Header Card */}
        <View style={styles.darkHeader}>
          <TouchableOpacity style={styles.backBtn} activeOpacity={0.8} onPress={() => router.back()}>
            <ArrowLeft size={22} color={Colors.white} strokeWidth={2.2} />
          </TouchableOpacity>
          <View style={styles.headerBody}>
            <View style={styles.headerTop}>
              <Text style={styles.tripId}>#{trip.ref_id ?? trip.id.slice(0, 8)}</Text>
              <StatusBadge status={statusLabel(trip.status)} />
            </View>
            <View style={styles.routeRow}>
              <View style={styles.routePoint}>
                <View style={styles.routeDotGreen} />
                <Text style={styles.routeCity} numberOfLines={2}>
                  {pickupStop ? `${pickupStop.location_lat.toFixed(3)}, ${pickupStop.location_lng.toFixed(3)}` : '—'}
                </Text>
              </View>
              <View style={styles.routeArrow}>
                <View style={styles.dashedLine} />
                <ArrowRight size={16} color={Colors.gray400} strokeWidth={2.2} />
              </View>
              <View style={styles.routePoint}>
                <View style={styles.routeDotOrange} />
                <Text style={styles.routeCity} numberOfLines={2}>
                  {dropoffStop ? `${dropoffStop.location_lat.toFixed(3)}, ${dropoffStop.location_lng.toFixed(3)}` : '—'}
                </Text>
              </View>
            </View>
            <View style={styles.headerStats}>
              <View style={styles.headerStat}>
                <Text style={styles.headerStatLabel}>Distance</Text>
                <Text style={styles.headerStatValue}>
                  {trip.planned_distance ? `${Math.round(trip.planned_distance)} km` : '—'}
                </Text>
              </View>
              <View style={styles.headerStat}>
                <Text style={styles.headerStatLabel}>Planned End</Text>
                <Text style={styles.headerStatValue}>{formatDateTime(trip.planned_end)}</Text>
              </View>
              <View style={styles.headerStat}>
                <Text style={styles.headerStatLabel}>Cargo</Text>
                <Text style={styles.headerStatValue} numberOfLines={1}>{trip.cargo_type}</Text>
              </View>
            </View>
          </View>
        </View>

        {/* Timeline */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Trip Timeline</Text>
          <Card style={styles.timeline}>
            {timeline.map((step, i) => (
              <View key={step.id} style={styles.timelineItem}>
                <View style={styles.timelineLeft}>
                  <View style={[
                    styles.timelineCircle,
                    step.done ? styles.timelineCircleDone : null,
                    step.active ? styles.timelineCircleActive : null,
                  ]}>
                    {step.done && !step.active && <Check size={14} color={Colors.white} strokeWidth={3} />}
                    {step.active && <View style={styles.timelinePulse} />}
                  </View>
                  {i < timeline.length - 1 && (
                    <View style={[styles.timelineLine, step.done ? styles.timelineLineDone : null]} />
                  )}
                </View>
                <View style={styles.timelineContent}>
                  <Text style={[styles.timelineLabel, step.active ? styles.timelineLabelActive : null]}>
                    {step.label}
                  </Text>
                  <Text style={styles.timelineTime}>{step.time}</Text>
                </View>
              </View>
            ))}
          </Card>
        </View>

        {/* Cargo Details */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Cargo Details</Text>
          <Card style={styles.detailCard}>
            {[
              { label: 'Description', value: trip.cargo_type },
              { label: 'Customer', value: trip.customer?.name ?? '—' },
              { label: 'Planned Start', value: formatDateTime(trip.planned_start) },
            ].map((row, i, arr) => (
              <View
                key={row.label}
                style={[styles.detailRow, i < arr.length - 1 ? styles.detailRowBorder : null]}
              >
                <Text style={styles.detailLabel}>{row.label}</Text>
                <Text style={styles.detailValue}>{row.value}</Text>
              </View>
            ))}
          </Card>
        </View>

        {/* Assignment Info */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Assignment</Text>
          <Card style={styles.assignCard}>
            <View style={styles.assignRow}>
              <Avatar
                initials={trip.driver ? `${trip.driver.first_name[0]}${trip.driver.last_name[0]}` : '?'}
                size={48}
              />
              <View style={styles.assignInfo}>
                <Text style={styles.assignName}>{driverName(trip)}</Text>
                <Text style={styles.assignRole}>
                  Driver{trip.driver?.ref_id ? ` · ${trip.driver.ref_id}` : ''}
                </Text>
              </View>
              {trip.driver?.phone_primary ? (
                <TouchableOpacity
                  style={styles.callBtn}
                  activeOpacity={0.8}
                  onPress={() => Linking.openURL(`tel:${trip.driver!.phone_primary}`).catch(() => {})}
                >
                  <Phone size={20} color={Colors.white} strokeWidth={2.2} />
                </TouchableOpacity>
              ) : null}
            </View>
            {trip.vehicle ? (
              <>
                <View style={styles.assignDivider} />
                <View style={styles.vehicleRow}>
                  <Truck size={22} color={Colors.gray600} strokeWidth={2} />
                  <View>
                    <Text style={styles.vehicleName}>
                      {trip.vehicle.plate_number} · {trip.vehicle.asset_type}
                    </Text>
                    {trip.vehicle.ref_id ? <Text style={styles.vehiclePlate}>{trip.vehicle.ref_id}</Text> : null}
                  </View>
                </View>
              </>
            ) : null}
          </Card>
        </View>

        {/* Actions */}
        {NEXT_STEP[trip.status] && (
          <View style={styles.actionsSection}>
            <Button
              variant="primary"
              label={advancing ? 'Updating…' : NEXT_STEP[trip.status]!.label}
              loading={advancing}
              onPress={handleAdvance}
            />
          </View>
        )}

        {ACTIVE_STATUSES.includes(trip.status) && (
          <View style={styles.actionsRow}>
            <Button
              variant="outline"
              label="Replace Driver"
              onPress={openReplaceDriver}
              style={styles.actionBtn}
            />
            <Button
              variant="danger"
              label={cancelling ? 'Cancelling…' : 'Cancel Trip'}
              loading={cancelling}
              onPress={handleCancelTrip}
              style={styles.actionBtn}
            />
          </View>
        )}

        <View style={styles.actionsSection}>
          <Button
            variant="outline"
            label="Track Live"
            iconLeft={<MapPin size={16} color={Colors.primary} strokeWidth={2.2} />}
            onPress={() => Alert.alert('Coming Soon', 'Live tracking will be available in a future update.')}
          />
        </View>
      </ScrollView>

      <Modal visible={showReplaceDriver} animationType="slide" transparent onRequestClose={() => setShowReplaceDriver(false)}>
        <View style={styles.modalOverlay}>
          <View style={styles.modalSheet}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Replace Driver</Text>
              <TouchableOpacity onPress={() => setShowReplaceDriver(false)} style={styles.modalClose}>
                <X size={20} color={Colors.gray900} strokeWidth={2.2} />
              </TouchableOpacity>
            </View>
            {loadingDrivers ? (
              <ActivityIndicator color={Colors.primary} style={{ marginVertical: Spacing.xl }} />
            ) : availableDrivers.length === 0 ? (
              <Text style={styles.emptyText}>No available drivers right now.</Text>
            ) : (
              <FlatList
                data={availableDrivers}
                keyExtractor={(d) => d.id}
                style={{ maxHeight: 360 }}
                renderItem={({ item }) => (
                  <TouchableOpacity
                    style={styles.driverRow}
                    activeOpacity={0.8}
                    disabled={replacingId !== null}
                    onPress={() => handleReplaceDriver(item.id)}
                  >
                    <Avatar initials={`${item.first_name[0] ?? ''}${item.last_name[0] ?? ''}`.toUpperCase()} size="md" />
                    <View style={{ flex: 1 }}>
                      <Text style={styles.driverRowName}>{item.first_name} {item.last_name}</Text>
                      <Text style={styles.driverRowId}>{item.ref_id ?? item.license_number}</Text>
                    </View>
                    {replacingId === item.id && <ActivityIndicator color={Colors.primary} />}
                  </TouchableOpacity>
                )}
              />
            )}
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  scroll: {
    paddingBottom: Spacing['3xl'],
  },
  darkHeader: {
    backgroundColor: Colors.darkCard,
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.lg,
    paddingBottom: Spacing['2xl'],
  },
  backBtn: {
    width: 40,
    height: 40,
    borderRadius: Radius.full,
    backgroundColor: 'rgba(255,255,255,0.15)',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Spacing.lg,
  },
  headerBody: {
    gap: Spacing.md,
  },
  headerTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  tripId: {
    fontSize: Typography.xl,
    fontWeight: '800',
    color: Colors.white,
    letterSpacing: 1,
  },
  routeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  routePoint: {
    flex: 1,
    alignItems: 'center',
    gap: 4,
  },
  routeDotGreen: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: Colors.success,
  },
  routeDotOrange: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: Colors.primary,
  },
  routeCity: {
    fontSize: Typography.xs,
    color: Colors.gray300,
    textAlign: 'center',
  },
  routeArrow: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 0.5,
  },
  dashedLine: {
    flex: 1,
    height: 1,
    backgroundColor: Colors.gray600,
  },
  headerStats: {
    flexDirection: 'row',
    borderTopWidth: 1,
    borderTopColor: Colors.gray800,
    paddingTop: Spacing.md,
  },
  headerStat: {
    flex: 1,
    alignItems: 'center',
  },
  headerStatLabel: {
    fontSize: Typography.xs,
    color: Colors.gray500,
    marginBottom: 2,
  },
  headerStatValue: {
    fontSize: Typography.sm,
    fontWeight: '700',
    color: Colors.white,
  },
  section: {
    padding: Spacing.lg,
    paddingBottom: 0,
  },
  sectionTitle: {
    fontSize: Typography.base,
    fontWeight: '700',
    color: Colors.gray900,
    marginBottom: Spacing.md,
  },
  timeline: {
    borderRadius: Radius.xl,
    padding: Spacing.lg,
  },
  timelineItem: {
    flexDirection: 'row',
    gap: Spacing.md,
  },
  timelineLeft: {
    alignItems: 'center',
    width: 24,
  },
  timelineCircle: {
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 2,
    borderColor: Colors.gray300,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.white,
  },
  timelineCircleDone: {
    backgroundColor: Colors.success,
    borderColor: Colors.success,
  },
  timelineCircleActive: {
    borderColor: Colors.primary,
    backgroundColor: Colors.white,
  },
  timelinePulse: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: Colors.primary,
  },
  timelineLine: {
    width: 2,
    flex: 1,
    minHeight: 24,
    backgroundColor: Colors.gray200,
    marginVertical: 2,
  },
  timelineLineDone: {
    backgroundColor: Colors.success,
  },
  timelineContent: {
    flex: 1,
    paddingBottom: Spacing.md,
  },
  timelineLabel: {
    fontSize: Typography.sm,
    fontWeight: '600',
    color: Colors.gray700,
  },
  timelineLabelActive: {
    color: Colors.primary,
    fontWeight: '700',
  },
  timelineTime: {
    fontSize: Typography.xs,
    color: Colors.gray400,
    marginTop: 2,
  },
  detailCard: {
    borderRadius: Radius.xl,
  },
  detailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
  },
  detailRowBorder: {
    borderBottomWidth: 1,
    borderBottomColor: Colors.gray100,
  },
  detailLabel: {
    fontSize: Typography.sm,
    color: Colors.gray500,
  },
  detailValue: {
    fontSize: Typography.sm,
    fontWeight: '700',
    color: Colors.gray900,
  },
  assignCard: {
    borderRadius: Radius.xl,
    padding: Spacing.lg,
  },
  assignRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    marginBottom: Spacing.md,
  },
  assignInfo: {
    flex: 1,
  },
  assignName: {
    fontSize: Typography.base,
    fontWeight: '700',
    color: Colors.gray900,
  },
  assignRole: {
    fontSize: Typography.xs,
    color: Colors.gray500,
    marginBottom: 3,
  },
  callBtn: {
    width: 40,
    height: 40,
    borderRadius: Radius.full,
    backgroundColor: Colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  assignDivider: {
    height: 1,
    backgroundColor: Colors.gray100,
    marginBottom: Spacing.md,
  },
  vehicleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
  },
  vehicleName: {
    fontSize: Typography.sm,
    fontWeight: '700',
    color: Colors.gray900,
  },
  vehiclePlate: {
    fontSize: Typography.xs,
    color: Colors.gray500,
    marginTop: 2,
  },
  actionsRow: {
    flexDirection: 'row',
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.md,
    gap: Spacing.md,
  },
  actionsSection: {
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.md,
  },
  actionBtn: {
    flex: 1,
  },
  emptyText: {
    fontSize: Typography.base,
    color: Colors.gray500,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.4)',
    justifyContent: 'flex-end',
  },
  modalSheet: {
    backgroundColor: Colors.white,
    borderTopLeftRadius: Radius['2xl'],
    borderTopRightRadius: Radius['2xl'],
    padding: Spacing.lg,
    paddingBottom: Spacing.xl,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: Spacing.md,
  },
  modalTitle: {
    fontSize: Typography.lg,
    fontWeight: '700',
    color: Colors.gray900,
  },
  modalClose: {
    width: 32,
    height: 32,
    borderRadius: Radius.full,
    backgroundColor: Colors.gray100,
    alignItems: 'center',
    justifyContent: 'center',
  },
  driverRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    paddingVertical: Spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: Colors.gray100,
  },
  driverRowName: {
    fontSize: Typography.sm,
    fontWeight: '700',
    color: Colors.gray900,
  },
  driverRowId: {
    fontSize: Typography.xs,
    color: Colors.gray500,
  },
});

export default TripDetailsScreen;
