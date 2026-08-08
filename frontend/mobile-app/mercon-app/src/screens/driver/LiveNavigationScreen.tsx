import React, { useEffect, useRef, useState } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, SafeAreaView, StatusBar, Alert, ActivityIndicator, Platform,
} from 'react-native';
import { useRouter } from 'expo-router';
import * as Location from 'expo-location';

let MapView: any = View;
let Marker: any = View;
let Polyline: any = View;
let PROVIDER_DEFAULT: any = undefined;

if (Platform.OS !== 'web') {
  try {
    const Maps = require('react-native-maps');
    MapView = Maps.default;
    Marker = Maps.Marker;
    Polyline = Maps.Polyline;
    PROVIDER_DEFAULT = Maps.PROVIDER_DEFAULT;
  } catch (e) {
    console.warn('react-native-maps load error:', e);
  }
}
import { ArrowLeft, MapPin, Truck, Siren } from 'lucide-react-native';
import { Colors, Spacing, Radius, Typography, Shadows } from '../../theme/tokens';
import { useCurrentTrip } from '../../lib/use-current-trip';
import { tripService } from '../../lib/trips';
import { getApiErrorMessage } from '../../lib/api';

const ARRIVAL_RADIUS_M = 200;
const OSM_TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';

/** Great-circle distance between two lat/lng points, in meters. */
function distanceMeters(lat1: number, lng1: number, lat2: number, lng2: number) {
  const R = 6371000;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLng = ((lng2 - lng1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

const LiveNavigationScreen = () => {
  const router = useRouter();
  const { trip, loading } = useCurrentTrip();
  const [position, setPosition] = useState<{ lat: number; lng: number } | null>(null);
  const [distanceToTarget, setDistanceToTarget] = useState<number | null>(null);
  const [routeCoords, setRouteCoords] = useState<{ latitude: number; longitude: number }[] | null>(null);
  const [baseDuration, setBaseDuration] = useState<number | null>(null);
  const [baseDistance, setBaseDistance] = useState<number | null>(null);
  const routeFetchedRef = useRef<string | null>(null);
  
  const [arriving, setArriving] = useState(false);
  const hasArrivedRef = useRef(false);
  const mapRef = useRef<MapView>(null);

  const isHeadingToPickup = trip?.status === 'Dispatched';
  const pickup = trip?.stops?.find((s) => s.stop_type === 'Pickup') ?? null;
  const dropoff = trip?.stops?.find((s) => s.stop_type === 'Dropoff') ?? null;
  
  const activeStop = isHeadingToPickup ? pickup : dropoff;
  const targetStatus = isHeadingToPickup ? 'AtPickup' : 'AtDelivery';
  const nextRoute = isHeadingToPickup ? '/trip/pickup' : '/trip/delivery';

  const goToStop = async () => {
    if (!trip || hasArrivedRef.current) return;
    hasArrivedRef.current = true;
    setArriving(true);
    try {
      await tripService.updateStatus(trip.id, targetStatus);
      router.replace(nextRoute as any);
    } catch (e) {
      hasArrivedRef.current = false;
      setArriving(false);
      Alert.alert('Could not update', getApiErrorMessage(e));
    }
  };

  // Stream live position and auto-detect arrival at the dropoff.
  useEffect(() => {
    let sub: Location.LocationSubscription | null = null;
    let cancelled = false;

    (async () => {
      const perm = await Location.requestForegroundPermissionsAsync();
      if (!perm.granted || cancelled) return;

      sub = await Location.watchPositionAsync(
        { accuracy: Location.Accuracy.High, timeInterval: 5000, distanceInterval: 10 },
        (loc) => {
          let lat = loc.coords.latitude;
          let lng = loc.coords.longitude;

          // HACK FOR DEVELOPMENT: If the iOS Simulator is stuck in San Francisco (Apple HQ),
          // teleport the driver to be near the active stop so the map looks realistic!
          if (Math.abs(lat - 37.785834) < 0.1 && Math.abs(lng - -122.406417) < 0.1) {
            if (activeStop) {
              lat = activeStop.location_lat - 0.005; // ~500m away
              lng = activeStop.location_lng - 0.005;
            }
          }

          setPosition({ lat, lng });

          if (activeStop) {
            const dist = distanceMeters(lat, lng, activeStop.location_lat, activeStop.location_lng);
            setDistanceToTarget(dist);
            if (dist <= ARRIVAL_RADIUS_M && !hasArrivedRef.current) goToStop();
          }
        },
      );
    })();

    return () => {
      cancelled = true;
      sub?.remove();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeStop?.id]);

  // Fetch the driving route from OSRM to draw the polyline and get ETA
  useEffect(() => {
    if (!position || !activeStop) return;
    if (routeFetchedRef.current === activeStop.id) return;

    routeFetchedRef.current = activeStop.id;
    const fetchRoute = async () => {
      try {
        const res = await fetch(
          `https://router.project-osrm.org/route/v1/driving/${position.lng},${position.lat};${activeStop.location_lng},${activeStop.location_lat}?overview=full&geometries=geojson`
        );
        const data = await res.json();
        if (data.code === 'Ok' && data.routes.length > 0) {
          const r = data.routes[0];
          setBaseDuration(r.duration);
          setBaseDistance(r.distance);
          setRouteCoords(r.geometry.coordinates.map((c: any) => ({
            latitude: c[1],
            longitude: c[0]
          })));
        }
      } catch (e) {
        console.warn('Failed to fetch route from OSRM:', e);
      }
    };
    fetchRoute();
  }, [position, activeStop]);

  // Frame both the driver and the active stop whenever they change.
  useEffect(() => {
    if (position && activeStop && mapRef.current && Platform.OS !== 'web' && mapRef.current.fitToCoordinates) {
      mapRef.current.fitToCoordinates(
        [
          { latitude: position.lat, longitude: position.lng },
          { latitude: activeStop.location_lat, longitude: activeStop.location_lng }
        ],
        { edgePadding: { top: 80, right: 80, bottom: 80, left: 80 }, animated: true }
      );
    }
  }, [position, activeStop]);

  if (loading && !trip) {
    return (
      <SafeAreaView style={[styles.container, styles.centerBox]}>
        <ActivityIndicator color={Colors.white} />
      </SafeAreaView>
    );
  }

  const center = position ?? (activeStop ? { lat: activeStop.location_lat, lng: activeStop.location_lng } : { lat: 24.7136, lng: 46.6753 });

  let displayEta = '';
  let displayDistance = '';
  if (baseDuration && baseDistance && distanceToTarget != null) {
    const ratio = Math.min(1, distanceToTarget / baseDistance);
    let secondsLeft = baseDuration * ratio;
    if (secondsLeft < 60 && distanceToTarget > 100) secondsLeft = 60; // minimum 1 min if not right there
    
    const mins = Math.round(secondsLeft / 60);
    displayEta = mins > 60 
      ? `${Math.floor(mins / 60)}h ${mins % 60}m` 
      : `${mins} min`;
      
    displayDistance = distanceToTarget > 1000 
      ? `${(distanceToTarget / 1000).toFixed(1)} km` 
      : `${Math.round(distanceToTarget)} m`;
  }

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor="#1A2B1A" />
      
      {/* Map implementation above... */}
      <View style={styles.mapContainer}>
        {Platform.OS === 'web' ? (
          <View style={[styles.map, styles.centerBox, { backgroundColor: '#1E293B' }]}>
            <MapPin size={36} color={Colors.primary} />
            <Text style={{ color: Colors.white, marginTop: 12, fontWeight: '700', fontSize: Typography.base }}>
              Live Map View
            </Text>
            <Text style={{ color: Colors.gray400, marginTop: 4, fontSize: Typography.xs }}>
              Open in Expo Go app on iOS/Android for interactive map
            </Text>
          </View>
        ) : (
          <MapView
            ref={mapRef}
            provider={PROVIDER_DEFAULT}
            style={styles.map}
            initialRegion={{
              latitude: center.lat,
              longitude: center.lng,
              latitudeDelta: 0.2,
              longitudeDelta: 0.2,
            }}
          >
            {/* Native vector map replaces OSM tiles for a premium Google Maps / Apple Maps look */}

            {position && (
              <Marker coordinate={{ latitude: position.lat, longitude: position.lng }} anchor={{ x: 0.5, y: 0.5 }}>
                <View style={styles.driverPin}>
                  <Truck size={16} color={Colors.white} strokeWidth={2.4} />
                </View>
              </Marker>
            )}

            {activeStop && (
              <Marker coordinate={{ latitude: activeStop.location_lat, longitude: activeStop.location_lng }} anchor={{ x: 0.5, y: 1 }}>
                <View style={styles.destPin}>
                  <MapPin size={18} color={Colors.white} strokeWidth={2.4} />
                </View>
              </Marker>
            )}

            {routeCoords && (
              <Polyline
                coordinates={routeCoords}
                strokeColor="#4285F4"
                strokeWidth={6}
                lineCap="round"
                lineJoin="round"
              />
            )}
          </MapView>
        )}

        <View style={styles.topOverlay}>
          <TouchableOpacity style={styles.backCircle} activeOpacity={0.8} onPress={() => router.back()}>
            <ArrowLeft size={22} color={Colors.gray900} strokeWidth={2.2} />
          </TouchableOpacity>
          <View style={styles.headerCard}>
            <Text style={styles.headerTitle}>#{trip?.ref_id ?? '—'}</Text>
            <Text style={styles.headerSub}>{trip?.customer?.name ?? 'Delivery in progress'}</Text>
          </View>
          <TouchableOpacity style={styles.sosCircle} activeOpacity={0.8} onPress={() => router.push('/trip/emergency')}>
            <Siren size={20} color={Colors.white} strokeWidth={2.4} />
          </TouchableOpacity>
        </View>

        {!position && (
          <View style={styles.gpsNotice}>
            <Text style={styles.gpsNoticeText}>Waiting for GPS signal…</Text>
          </View>
        )}
      </View>

      <View style={styles.bottomCard}>
        {distanceToTarget != null ? (
          <View style={styles.navStats}>
            <Text style={styles.navEta}>{displayEta}</Text>
            <Text style={styles.navDistance}>{displayDistance}</Text>
          </View>
        ) : (
          <Text style={styles.navDistance}>Calculating route...</Text>
        )}
        
        {distanceToTarget != null && distanceToTarget <= 2000 && (
          <TouchableOpacity
            style={[styles.arrivedBtn, arriving && { opacity: 0.6 }]}
            activeOpacity={0.8}
            onPress={goToStop}
            disabled={arriving}
          >
            <Text style={styles.arrivedBtnText}>{arriving ? 'Updating…' : "I've Arrived"}</Text>
          </TouchableOpacity>
        )}
      </View>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#1A2B1A',
  },
  centerBox: { alignItems: 'center', justifyContent: 'center' },
  mapContainer: {
    flex: 1,
    position: 'relative',
  },
  map: {
    ...StyleSheet.absoluteFill,
  },
  driverPin: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: Colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: Colors.white,
  },
  destPin: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: '#1A2B1A',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: Colors.white,
  },
  topOverlay: {
    position: 'absolute',
    top: Spacing.lg,
    left: Spacing.lg,
    right: Spacing.lg,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  backCircle: {
    width: 40,
    height: 40,
    borderRadius: Radius.full,
    backgroundColor: Colors.white,
    alignItems: 'center',
    justifyContent: 'center',
    ...Shadows.md,
  },
  headerCard: {
    flex: 1,
    backgroundColor: Colors.white,
    borderRadius: Radius.lg,
    padding: Spacing.sm,
    paddingHorizontal: Spacing.md,
    ...Shadows.md,
  },
  sosCircle: {
    width: 40,
    height: 40,
    borderRadius: Radius.full,
    backgroundColor: Colors.error,
    alignItems: 'center',
    justifyContent: 'center',
    ...Shadows.md,
  },
  headerTitle: {
    fontSize: Typography.sm,
    fontWeight: '800',
    color: Colors.gray900,
  },
  headerSub: {
    fontSize: Typography.xs,
    color: Colors.gray500,
  },
  gpsNotice: {
    position: 'absolute',
    bottom: Spacing.lg,
    alignSelf: 'center',
    backgroundColor: 'rgba(0,0,0,0.65)',
    borderRadius: Radius.lg,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
  },
  gpsNoticeText: {
    color: Colors.white,
    fontSize: Typography.xs,
    fontWeight: '600',
  },
  bottomCard: {
    backgroundColor: Colors.white,
    padding: Spacing.lg,
    paddingBottom: Spacing.xl + 12, // Extra padding for SafeArea
    borderTopLeftRadius: Radius.xl,
    borderTopRightRadius: Radius.xl,
    ...Shadows.lg,
  },
  navStats: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: Spacing.sm,
    marginBottom: Spacing.md,
  },
  navEta: {
    fontSize: 28,
    fontWeight: '800',
    color: '#0F9D58', // Google Maps Green
  },
  navDistance: {
    fontSize: Typography.base,
    color: Colors.gray500,
    fontWeight: '600',
  },
  arrivedBtn: {
    backgroundColor: Colors.primary,
    borderRadius: Radius.xl,
    paddingVertical: Spacing.md,
    alignItems: 'center',
  },
  arrivedBtnText: {
    color: Colors.white,
    fontWeight: '700',
    fontSize: Typography.base,
  },
});

export default LiveNavigationScreen;
