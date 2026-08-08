import React, { useCallback, useState } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity, ImageBackground,
  StyleSheet, SafeAreaView, StatusBar, RefreshControl, ActivityIndicator, Alert,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { MapPin, Hand, Siren } from 'lucide-react-native';
import { Colors, Spacing, Radius, Typography, Shadows } from '../../theme/tokens';
import { Badge, DarkCard } from '../../components';
import { useAuth } from '../../lib/auth-context';
import { useCurrentTrip } from '../../lib/use-current-trip';
import { tripService, NEXT_STEP, PHOTO_FOR, statusLabel, type TripStatus } from '../../lib/trips';
import { choosePhoto } from '../../lib/camera';
import { getApiErrorMessage } from '../../lib/api';

// eslint-disable-next-line @typescript-eslint/no-var-requires
const homeBg = require('../../../assets/images/home-bg.png');

/** Badge colour by trip status. */
function statusVariant(s: TripStatus): 'warning' | 'success' | 'info' | 'neutral' {
  if (s === 'InTransit') return 'warning';
  if (s === 'Completed') return 'success';
  if (s === 'AtPickup' || s === 'AtDelivery') return 'info';
  return 'neutral';
}

/** Short "27 Jul, 14:30" label, or a fallback when there's no timestamp. */
function shortWhen(iso?: string | null, fallback = 'Scheduled'): string {
  if (!iso) return fallback;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return fallback;
  return d.toLocaleString(undefined, { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
}

const HomeScreen = () => {
  const { profile, signOut } = useAuth();
  const { trip, loading, error, refetch, setTrip } = useCurrentTrip();
  const [activeTab, setActiveTab] = useState('Home');
  const [advancing, setAdvancing] = useState(false);
  const router = useRouter();

  // Refresh the trip whenever Home regains focus (e.g. returning from a step screen).
  useFocusEffect(useCallback(() => { refetch(); }, [refetch]));

  const firstName = (profile?.name || 'Driver').split(' ')[0];

  const next = trip ? NEXT_STEP[trip.status] : undefined;

  const doAdvance = async () => {
    if (!trip || !next) return;
    const photoKind = PHOTO_FOR[next.to];
    setAdvancing(true);
    try {
      // Some transitions require a photo first (cargo before In Transit, POD before Completed).
      if (photoKind) {
        const photo = await choosePhoto();
        if (!photo) { setAdvancing(false); return; } // user cancelled the camera
        await tripService.uploadPhoto(trip.id, photoKind, photo);
      }
      const updated = await tripService.updateStatus(trip.id, next.to);
      // Completed trips drop out of "current", so clear the card.
      setTrip(updated.status === 'Completed' ? null : updated);
    } catch (e) {
      Alert.alert('Could not update', getApiErrorMessage(e));
    } finally {
      setAdvancing(false);
    }
  };

  const advance = () => {
    if (!trip || !next) return;
    // The pickup and arrival steps have their own screens.
    if (trip.status === 'Dispatched') { router.push('/trip/navigate'); return; }
    if (trip.status === 'AtPickup') { router.push('/trip/pickup'); return; }
    if (trip.status === 'InTransit') { router.push('/trip/navigate'); return; }
    if (trip.status === 'AtDelivery') { router.push('/trip/delivery'); return; }
    const photoKind = PHOTO_FOR[next.to];
    const msg = photoKind
      ? `You'll take a ${photoKind === 'pod' ? 'delivery (POD)' : 'cargo'} photo, then mark the trip as "${statusLabel(next.to)}".`
      : `Mark this trip as "${statusLabel(next.to)}"?`;
    Alert.alert('Confirm', msg, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Continue', onPress: doAdvance },
    ]);
  };

  return (
    <ImageBackground source={homeBg} style={styles.bg} resizeMode="cover">
      <SafeAreaView style={styles.safe}>
      <StatusBar barStyle="dark-content" backgroundColor={Colors.white} />
      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={refetch} tintColor={Colors.primary} />}
      >
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.greeting}>Welcome back,</Text>
            <View style={styles.nameRow}>
              <Text style={styles.driverName}>{firstName}</Text>
              <Hand size={20} color="#F5A623" strokeWidth={2.2} />
            </View>
          </View>
          <View style={styles.headerActions}>
            <TouchableOpacity
              onPress={() => router.push('/trip/emergency')}
              activeOpacity={0.7}
              style={styles.sosBtn}
            >
              <Siren size={16} color={Colors.white} strokeWidth={2.4} />
              <Text style={styles.sosText}>SOS</Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={signOut} activeOpacity={0.7} style={styles.signOutBtn}>
              <Text style={styles.signOutText}>Sign out</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Active trip — centered in the remaining page space, whichever state renders */}
        <View style={styles.tripSection}>
          {loading && !trip ? (
            <View style={styles.centerBox}>
              <ActivityIndicator color={Colors.primary} />
            </View>
          ) : error ? (
            <View style={styles.centerBox}>
              <Text style={styles.errorText}>{error}</Text>
              <TouchableOpacity onPress={refetch}><Text style={styles.retryText}>Tap to retry</Text></TouchableOpacity>
            </View>
          ) : !trip ? (
            <View style={styles.emptyCard}>
              <Text style={styles.emptyTitle}>No active trip</Text>
              <Text style={styles.emptySub}>You're all caught up. Waiting for your next assignment.</Text>
            </View>
          ) : (
            <DarkCard style={styles.jobCard}>
              <View style={styles.jobHeader}>
                <View style={styles.jobHeaderLeft}>
                  <Text style={styles.jobLabel}>ACTIVE TRIP</Text>
                  <Text style={styles.jobId} numberOfLines={1}>#{trip.ref_id ?? trip.id.slice(0, 8)}</Text>
                </View>
                <Badge label={statusLabel(trip.status)} variant={statusVariant(trip.status)} />
              </View>

              {/* Route timeline */}
              <View style={styles.route}>
                <View style={styles.routeRail}>
                  <View style={styles.dotPickup} />
                  <View style={styles.railLine} />
                  <MapPin size={18} color={Colors.primary} strokeWidth={2.4} />
                </View>
                <View style={styles.routeCol}>
                  <View style={styles.routeStop}>
                    <Text style={styles.routeStage}>PICKUP</Text>
                    <Text style={styles.routeWhen} numberOfLines={1}>{shortWhen(trip.planned_start)}</Text>
                  </View>
                  <View style={[styles.routeStop, styles.routeStopLast]}>
                    <Text style={styles.routeStage}>DELIVERY</Text>
                    <Text style={styles.routeWhen} numberOfLines={1}>{shortWhen(trip.planned_end)}</Text>
                  </View>
                </View>
              </View>

              <View style={styles.divider} />

              <View style={styles.jobMeta}>
                <View style={styles.metaItem}>
                  <Text style={styles.metaLabel}>Customer</Text>
                  <Text style={styles.metaValue} numberOfLines={1}>{trip.customer?.name ?? '—'}</Text>
                </View>
                <View style={styles.metaItem}>
                  <Text style={styles.metaLabel}>Cargo</Text>
                  <Text style={styles.metaValue} numberOfLines={1}>{trip.cargo_type}</Text>
                </View>
                <View style={[styles.metaItem, styles.metaItemLast]}>
                  <Text style={styles.metaLabel}>Distance</Text>
                  <Text style={styles.metaValue} numberOfLines={1}>{trip.planned_distance ? `${trip.planned_distance} km` : '—'}</Text>
                </View>
              </View>

              {next ? (
                <TouchableOpacity
                  style={[styles.startBtn, advancing && { opacity: 0.6 }]}
                  activeOpacity={0.8}
                  onPress={advance}
                  disabled={advancing}
                >
                  <Text style={styles.startBtnText}>{advancing ? 'Updating…' : next.label}</Text>
                </TouchableOpacity>
              ) : trip.status === 'Draft' ? (
                <Text style={styles.doneNote}>Awaiting dispatch — your operator will assign a vehicle and start this trip.</Text>
              ) : (
                <Text style={styles.doneNote}>This trip is {statusLabel(trip.status).toLowerCase()}.</Text>
              )}
            </DarkCard>
          )}
        </View>
      </ScrollView>
      </SafeAreaView>
    </ImageBackground>
  );
};

const styles = StyleSheet.create({
  bg: {
    flex: 1,
    backgroundColor: Colors.gray100,
  },
  safe: {
    flex: 1,
    backgroundColor: 'transparent',
  },
  scroll: {
    padding: Spacing.lg,
    paddingBottom: Spacing['3xl'],
    flexGrow: 1,
  },
  // Fills the space below the header; centers whichever trip state renders
  // (empty banner or the trip card) at the same vertical spot on the page.
  tripSection: {
    flex: 1,
    justifyContent: 'center',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: Spacing.xl,
  },
  greeting: { fontSize: Typography.sm, color: Colors.gray500 },
  nameRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  driverName: { fontSize: Typography.xl, fontWeight: '700', color: Colors.gray900 },
  signOutBtn: { paddingVertical: Spacing.xs, paddingHorizontal: Spacing.sm },
  signOutText: { fontSize: Typography.sm, color: Colors.primary, fontWeight: '600' },
  headerActions: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  sosBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: Colors.error,
    borderRadius: Radius.full,
    paddingVertical: 6,
    paddingHorizontal: Spacing.sm,
    ...Shadows.sm,
  },
  sosText: { fontSize: Typography.xs, fontWeight: '800', color: Colors.white },

  centerBox: { paddingVertical: Spacing['3xl'], alignItems: 'center', gap: Spacing.sm },
  errorText: { fontSize: Typography.sm, color: Colors.error, textAlign: 'center' },
  retryText: { fontSize: Typography.sm, color: Colors.primary, fontWeight: '600' },

  emptyCard: {
    backgroundColor: Colors.white,
    borderRadius: Radius.xl,
    padding: Spacing.xl,
    alignItems: 'center',
    ...Shadows.sm,
  },
  emptyTitle: { fontSize: Typography.lg, fontWeight: '700', color: Colors.gray900, marginBottom: Spacing.xs },
  emptySub: { fontSize: Typography.sm, color: Colors.gray500, textAlign: 'center' },

  jobCard: { marginBottom: Spacing.lg, padding: Spacing.lg },
  jobHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: Spacing.lg,
    gap: Spacing.sm,
  },
  jobHeaderLeft: { flex: 1 },
  jobLabel: { fontSize: Typography.xs, color: Colors.gray400, letterSpacing: 1.5, fontWeight: '700', marginBottom: 2 },
  jobId: { fontSize: Typography.xl, fontWeight: '800', color: Colors.white },

  // Route timeline
  route: { flexDirection: 'row', gap: Spacing.md },
  routeRail: { alignItems: 'center', paddingTop: 4 },
  dotPickup: {
    width: 12, height: 12, borderRadius: 6,
    borderWidth: 3, borderColor: Colors.success ?? '#22C55E', backgroundColor: 'transparent',
  },
  railLine: { width: 2, flex: 1, minHeight: 22, backgroundColor: Colors.gray700, marginVertical: 4 },
  routeCol: { flex: 1 },
  routeStop: { marginBottom: Spacing.lg },
  routeStopLast: { marginBottom: 0 },
  routeStage: { fontSize: Typography.xs, color: Colors.gray400, letterSpacing: 1, fontWeight: '700' },
  routeWhen: { fontSize: Typography.base, fontWeight: '700', color: Colors.white, marginTop: 2 },

  divider: { height: 1, backgroundColor: Colors.gray700, marginVertical: Spacing.lg },

  jobMeta: { flexDirection: 'row', marginBottom: Spacing.lg },
  metaItem: { flex: 1, paddingRight: Spacing.sm },
  metaItemLast: { paddingRight: 0 },
  metaLabel: { fontSize: Typography.xs, color: Colors.gray400, marginBottom: 3 },
  metaValue: { fontSize: Typography.sm, color: Colors.white, fontWeight: '700' },
  startBtn: { backgroundColor: Colors.primary, borderRadius: Radius.lg, paddingVertical: Spacing.md, alignItems: 'center' },
  startBtnText: { color: Colors.white, fontWeight: '700', fontSize: Typography.base },
  doneNote: { color: Colors.gray400, fontSize: Typography.sm, textAlign: 'center' },
});

export default HomeScreen;
