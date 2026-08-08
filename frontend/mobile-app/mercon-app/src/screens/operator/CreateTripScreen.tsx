import React, { useEffect, useState } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity,
  StyleSheet, SafeAreaView, StatusBar, ActivityIndicator, Alert,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { ArrowLeft, Check, Truck } from 'lucide-react-native';
import { Colors, Spacing, Radius, Typography } from '../../theme/tokens';
import { Button, Card, Input, StatusBadge } from '../../components';
import { getApiErrorMessage } from '../../lib/api';
import {
  operatorService, invalidateOperatorTrips,
  type OperatorCustomer, type OperatorDriver, type OperatorVehicle,
} from '../../lib/operator';

const CreateTripScreen = () => {
  const router = useRouter();
  // Optional: set when arriving from a customer's "Create Trip" action, so the
  // customer arrives pre-selected instead of having to be found in the list.
  const { customerId: presetCustomerId } = useLocalSearchParams<{ customerId?: string }>();

  const [loadingOptions, setLoadingOptions] = useState(true);
  const [optionsError, setOptionsError] = useState<string | null>(null);
  const [customers, setCustomers] = useState<OperatorCustomer[]>([]);
  const [drivers, setDrivers] = useState<OperatorDriver[]>([]);
  const [vehicles, setVehicles] = useState<OperatorVehicle[]>([]);

  const [customerId, setCustomerId] = useState(presetCustomerId ?? '');
  const [pickupLat, setPickupLat] = useState('');
  const [pickupLng, setPickupLng] = useState('');
  const [dropoffLat, setDropoffLat] = useState('');
  const [dropoffLng, setDropoffLng] = useState('');
  const [pickupName, setPickupName] = useState('');
  const [dropoffName, setDropoffName] = useState('');
  const [date, setDate] = useState('');
  const [time, setTime] = useState('');
  const [etaDate, setEtaDate] = useState('');
  const [etaTime, setEtaTime] = useState('');
  const [cargoDesc, setCargoDesc] = useState('');
  const [selectedDriver, setSelectedDriver] = useState('');
  const [selectedVehicle, setSelectedVehicle] = useState('');

  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    (async () => {
      setLoadingOptions(true);
      setOptionsError(null);
      try {
        const [c, d, v] = await Promise.all([
          operatorService.customers(),
          operatorService.availableDrivers(),
          operatorService.availableVehicles(),
        ]);
        setCustomers(c);
        setDrivers(d);
        setVehicles(v);
      } catch (e) {
        setOptionsError(getApiErrorMessage(e));
      } finally {
        setLoadingOptions(false);
      }
    })();
  }, []);

  const pickupLatNum = parseFloat(pickupLat);
  const pickupLngNum = parseFloat(pickupLng);
  const dropoffLatNum = parseFloat(dropoffLat);
  const dropoffLngNum = parseFloat(dropoffLng);
  const hasValidCoords =
    !Number.isNaN(pickupLatNum) && !Number.isNaN(pickupLngNum) &&
    !Number.isNaN(dropoffLatNum) && !Number.isNaN(dropoffLngNum);

  const isValid = !!customerId && !!cargoDesc && !!selectedDriver && !!selectedVehicle && hasValidCoords;

  // date: DD/MM/YYYY, time: HH:MM — both optional, best-effort parse.
  function parseDateTime(dateStr: string, timeStr: string): string | undefined {
    const dateMatch = dateStr.trim().match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
    if (!dateMatch) return undefined;
    const [, dd, mm, yyyy] = dateMatch;
    const timeMatch = timeStr.trim().match(/^(\d{1,2}):(\d{2})$/) ?? ['', '0', '0'];
    const [, hh, min] = timeMatch;
    const d = new Date(Number(yyyy), Number(mm) - 1, Number(dd), Number(hh), Number(min));
    return Number.isNaN(d.getTime()) ? undefined : d.toISOString();
  }

  const handleSubmit = async () => {
    if (!isValid || submitting) return;

    const plannedPickup = parseDateTime(date, time);
    const plannedDropoff = parseDateTime(etaDate, etaTime);

    // Matches CreateTripPage's ordering check on the web: a delivery due
    // before its own collection produces a permanently "late" trip that no
    // driver could ever have run on time.
    if (plannedPickup && plannedDropoff && plannedDropoff <= plannedPickup) {
      Alert.alert('Check the times', 'Delivery due must be after the departure time.');
      return;
    }

    setSubmitting(true);
    try {
      await operatorService.createTrip({
        customer_id: customerId,
        driver_id: selectedDriver,
        vehicle_id: selectedVehicle,
        cargo_type: cargoDesc,
        planned_start: plannedPickup,
        // Both planned times are what every delay figure is measured against.
        // Omitting them (as this screen used to) creates a trip that can never
        // be counted as late, so it silently vanishes from the delay reports.
        stops: [
          {
            stop_type: 'Pickup', lat: pickupLatNum, lng: pickupLngNum,
            planned_arrival: plannedPickup,
            location_name: pickupName.trim() || undefined,
          },
          {
            stop_type: 'Dropoff', lat: dropoffLatNum, lng: dropoffLngNum,
            planned_arrival: plannedDropoff,
            location_name: dropoffName.trim() || undefined,
          },
        ],
      });
      invalidateOperatorTrips();
      router.back();
    } catch (e) {
      Alert.alert('Could not create trip', getApiErrorMessage(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.gray100 }}>
      <StatusBar barStyle="dark-content" backgroundColor={Colors.white} />

      <View style={styles.header}>
        <TouchableOpacity style={styles.backBtn} activeOpacity={0.8} onPress={() => router.back()}>
          <ArrowLeft size={22} color={Colors.gray900} strokeWidth={2.2} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Create New Trip</Text>
        <View style={styles.placeholder} />
      </View>

      {loadingOptions ? (
        <ActivityIndicator color={Colors.primary} style={{ marginTop: Spacing['3xl'] }} />
      ) : (
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          {optionsError ? <Text style={styles.errorText}>{optionsError}</Text> : null}

          {/* Section: Customer */}
          <Text style={styles.sectionTitle}>Customer</Text>
          <Card style={styles.pickerCard}>
            {customers.length === 0 ? (
              <Text style={styles.emptyHint}>No customers found</Text>
            ) : (
              customers.map((c) => (
                <TouchableOpacity
                  key={c.id}
                  style={[styles.pickerItem, customerId === c.id ? styles.pickerItemActive : null]}
                  activeOpacity={0.8}
                  onPress={() => setCustomerId(c.id)}
                >
                  <Text style={[styles.pickerItemText, customerId === c.id ? styles.pickerItemTextActive : null]}>
                    {c.name}
                  </Text>
                  {customerId === c.id && <Check size={18} color={Colors.primary} strokeWidth={3} />}
                </TouchableOpacity>
              ))
            )}
          </Card>

          {/* Section: Route */}
          <Text style={styles.sectionTitle}>Route</Text>
          <Card style={styles.formCard}>
            <View style={styles.formGroup}>
              <Text style={styles.label}>Pickup Coordinates (lat, lng)</Text>
              <View style={styles.rowFields}>
                <Input
                  style={{ flex: 1 }}
                  value={pickupLat}
                  onChangeText={setPickupLat}
                  placeholder="Latitude"
                  keyboardType="numeric"
                />
                <Input
                  style={{ flex: 1 }}
                  value={pickupLng}
                  onChangeText={setPickupLng}
                  placeholder="Longitude"
                  keyboardType="numeric"
                />
              </View>
              <Input
                label="Location name"
                value={pickupName}
                onChangeText={setPickupName}
                placeholder="e.g. Khamis Sorting Center"
                maxLength={120}
              />
            </View>
            <View style={styles.formDivider} />
            <View style={styles.formGroup}>
              <Text style={styles.label}>Dropoff Coordinates (lat, lng)</Text>
              <View style={styles.rowFields}>
                <Input
                  style={{ flex: 1 }}
                  value={dropoffLat}
                  onChangeText={setDropoffLat}
                  placeholder="Latitude"
                  keyboardType="numeric"
                />
                <Input
                  style={{ flex: 1 }}
                  value={dropoffLng}
                  onChangeText={setDropoffLng}
                  placeholder="Longitude"
                  keyboardType="numeric"
                />
              </View>
              <Input
                label="Location name"
                value={dropoffName}
                onChangeText={setDropoffName}
                placeholder="e.g. Baish"
                maxLength={120}
              />
            </View>
          </Card>

          {/* Section: Date & Time */}
          <Text style={styles.sectionTitle}>Departure (Optional)</Text>
          <Card style={styles.formCard}>
            <View style={styles.rowFields}>
              <Input
                style={{ flex: 1 }}
                label="Date"
                value={date}
                onChangeText={setDate}
                placeholder="DD/MM/YYYY"
                keyboardType="numeric"
              />
              <Input
                style={{ flex: 1 }}
                label="Time"
                value={time}
                onChangeText={setTime}
                placeholder="HH:MM"
                keyboardType="numeric"
              />
            </View>
          </Card>

          {/* Delivery due — the baseline every delay figure is measured from. */}
          <Text style={styles.sectionTitle}>Delivery Due (Optional)</Text>
          <Card style={styles.formCard}>
            <View style={styles.rowFields}>
              <Input
                style={{ flex: 1 }}
                label="Date"
                value={etaDate}
                onChangeText={setEtaDate}
                placeholder="DD/MM/YYYY"
                keyboardType="numeric"
              />
              <Input
                style={{ flex: 1 }}
                label="Time"
                value={etaTime}
                onChangeText={setEtaTime}
                placeholder="HH:MM"
                keyboardType="numeric"
              />
            </View>
          </Card>

          {/* Section: Cargo */}
          <Text style={styles.sectionTitle}>Cargo</Text>
          <Card style={styles.formCard}>
            <Input
              label="Description"
              value={cargoDesc}
              onChangeText={setCargoDesc}
              placeholder="e.g. Consumer Electronics"
            />
          </Card>

          {/* Section: Driver */}
          <Text style={styles.sectionTitle}>Assign Driver</Text>
          <Card style={styles.pickerCard}>
            {drivers.length === 0 ? (
              <Text style={styles.emptyHint}>No available drivers</Text>
            ) : (
              drivers.map((driver) => (
                <TouchableOpacity
                  key={driver.id}
                  style={[styles.driverItem, selectedDriver === driver.id ? styles.driverItemActive : null]}
                  activeOpacity={0.8}
                  onPress={() => setSelectedDriver(driver.id)}
                >
                  <View style={styles.driverAvatar}>
                    <Text style={styles.driverAvatarText}>
                      {`${driver.first_name[0] ?? ''}${driver.last_name[0] ?? ''}`.toUpperCase()}
                    </Text>
                  </View>
                  <View style={styles.driverInfo}>
                    <Text style={styles.driverName}>{driver.first_name} {driver.last_name}</Text>
                    <Text style={styles.driverId}>{driver.ref_id ?? driver.license_number}</Text>
                  </View>
                  <StatusBadge status="Available" />
                </TouchableOpacity>
              ))
            )}
          </Card>

          {/* Section: Vehicle */}
          <Text style={styles.sectionTitle}>Assign Vehicle</Text>
          <Card style={styles.pickerCard}>
            {vehicles.length === 0 ? (
              <Text style={styles.emptyHint}>No available vehicles</Text>
            ) : (
              vehicles.map((v) => (
                <TouchableOpacity
                  key={v.id}
                  style={[styles.driverItem, selectedVehicle === v.id ? styles.driverItemActive : null]}
                  activeOpacity={0.8}
                  onPress={() => setSelectedVehicle(v.id)}
                >
                  <View style={[styles.driverAvatar, styles.vehicleAvatarBg]}>
                    <Truck size={22} color={Colors.primary} strokeWidth={2} />
                  </View>
                  <View style={styles.driverInfo}>
                    <Text style={styles.driverName}>{v.plate_number}</Text>
                    <Text style={styles.driverId}>{v.asset_type}</Text>
                  </View>
                  <StatusBadge status="Available" />
                </TouchableOpacity>
              ))
            )}
          </Card>

          <Button
            title={submitting ? 'Creating…' : 'Create Trip'}
            onPress={handleSubmit}
            disabled={!isValid || submitting}
            loading={submitting}
          />

          {!isValid && (
            <Text style={styles.validationHint}>
              Fill in customer, cargo, pickup/dropoff coordinates, driver and vehicle to create the trip.
            </Text>
          )}
        </ScrollView>
      )}
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  header: {
    backgroundColor: Colors.white,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: Colors.gray100,
  },
  backBtn: {
    width: 40,
    height: 40,
    borderRadius: Radius.full,
    backgroundColor: Colors.gray100,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerTitle: {
    fontSize: Typography.lg,
    fontWeight: '700',
    color: Colors.gray900,
  },
  placeholder: {
    width: 40,
  },
  scroll: {
    padding: Spacing.lg,
    paddingBottom: Spacing['3xl'],
    gap: Spacing.sm,
  },
  errorText: {
    fontSize: Typography.sm,
    color: Colors.error,
    marginBottom: Spacing.sm,
  },
  sectionTitle: {
    fontSize: Typography.sm,
    fontWeight: '700',
    color: Colors.gray500,
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginTop: Spacing.md,
    marginBottom: Spacing.xs,
  },
  pickerCard: {
    borderRadius: Radius.xl,
  },
  emptyHint: {
    padding: Spacing.lg,
    fontSize: Typography.sm,
    color: Colors.gray500,
  },
  pickerItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: Colors.gray100,
  },
  pickerItemActive: {
    backgroundColor: Colors.primaryLight,
  },
  pickerItemText: {
    fontSize: Typography.sm,
    color: Colors.gray700,
    fontWeight: '500',
  },
  pickerItemTextActive: {
    color: Colors.primary,
    fontWeight: '700',
  },
  formCard: {
    borderRadius: Radius.xl,
    padding: Spacing.lg,
  },
  formGroup: {
    gap: Spacing.xs,
  },
  label: {
    fontSize: Typography.xs,
    color: Colors.gray500,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  formDivider: {
    height: Spacing.md,
  },
  rowFields: {
    flexDirection: 'row',
    gap: Spacing.lg,
  },
  driverItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    gap: Spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: Colors.gray100,
  },
  driverItemActive: {
    backgroundColor: Colors.primaryLight,
  },
  driverAvatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: Colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  driverAvatarText: {
    fontSize: Typography.sm,
    fontWeight: '700',
    color: Colors.white,
  },
  vehicleAvatarBg: {
    backgroundColor: Colors.gray200,
  },
  driverInfo: {
    flex: 1,
  },
  driverName: {
    fontSize: Typography.sm,
    fontWeight: '700',
    color: Colors.gray900,
  },
  driverId: {
    fontSize: Typography.xs,
    color: Colors.gray500,
  },
  validationHint: {
    fontSize: Typography.xs,
    color: Colors.gray400,
    textAlign: 'center',
    marginTop: -Spacing.xs,
  },
});

export default CreateTripScreen;
