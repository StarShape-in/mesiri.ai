import React, { useEffect, useState } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity,
  StyleSheet, SafeAreaView, StatusBar, ActivityIndicator, Alert,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { ArrowLeft } from 'lucide-react-native';
import { Colors, Spacing, Radius, Typography } from '../../theme/tokens';
import { Button, Card, Input, FilterChip } from '../../components';
import { getApiErrorMessage } from '../../lib/api';
import {
  operatorService, invalidateOperatorVehicles, useOperatorVehicleById,
  type UpdateVehicleInput,
} from '../../lib/operator';

const ASSET_TYPES: UpdateVehicleInput['asset_type'][] = ['Flatbed', 'Reefer', 'Box', 'Tanker'];
const STATUSES: UpdateVehicleInput['status'][] = ['Available', 'OnTrip', 'Maintenance', 'Inactive'];
const STATUS_LABELS: Record<string, string> = {
  Available: 'Available',
  OnTrip: 'On Trip',
  Maintenance: 'Maintenance',
  Inactive: 'Inactive',
};

const VehicleEditScreen = () => {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { vehicle, loading, error } = useOperatorVehicleById(id);

  const [plateNumber, setPlateNumber] = useState('');
  const [assetType, setAssetType] = useState<UpdateVehicleInput['asset_type']>('Flatbed');
  const [capacityKg, setCapacityKg] = useState('');
  const [status, setStatus] = useState<UpdateVehicleInput['status']>('Available');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!vehicle) return;
    setPlateNumber(vehicle.plate_number);
    setAssetType((vehicle.asset_type as UpdateVehicleInput['asset_type']) ?? 'Flatbed');
    setCapacityKg(String(vehicle.capacity_kg ?? ''));
    setStatus((vehicle.status as UpdateVehicleInput['status']) ?? 'Available');
  }, [vehicle]);

  const handleSave = async () => {
    if (!id || saving) return;
    setSaving(true);
    try {
      const capacityNum = parseInt(capacityKg, 10);
      const payload: UpdateVehicleInput = {
        plate_number: plateNumber.trim() || undefined,
        asset_type: assetType,
        capacity_kg: Number.isFinite(capacityNum) && capacityNum > 0 ? capacityNum : undefined,
        status,
      };
      await operatorService.updateVehicle(id, payload);
      invalidateOperatorVehicles();
      router.back();
    } catch (e) {
      Alert.alert('Could not save vehicle', getApiErrorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.gray100 }}>
      <StatusBar barStyle="dark-content" backgroundColor={Colors.white} />
      <View style={styles.header}>
        <TouchableOpacity style={styles.backBtn} activeOpacity={0.8} onPress={() => router.back()}>
          <ArrowLeft size={22} color={Colors.gray900} strokeWidth={2.2} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Edit Vehicle</Text>
        <View style={styles.placeholder} />
      </View>

      {loading && !vehicle ? (
        <ActivityIndicator color={Colors.primary} style={{ marginTop: Spacing['3xl'] }} />
      ) : !vehicle ? (
        <Text style={styles.errorText}>{error ?? 'Vehicle not found'}</Text>
      ) : (
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          <Text style={styles.sectionTitle}>Identity</Text>
          <Card style={styles.formCard}>
            <Input label="Plate Number" value={plateNumber} onChangeText={setPlateNumber} autoCapitalize="characters" />
            <View style={styles.formDivider} />
            <Input label="Capacity (kg)" value={capacityKg} onChangeText={setCapacityKg} keyboardType="numeric" />
          </Card>

          <Text style={styles.sectionTitle}>Asset Type</Text>
          <View style={styles.chipRow}>
            {ASSET_TYPES.map((t) => (
              <FilterChip key={t} label={t!} active={assetType === t} onPress={() => setAssetType(t)} />
            ))}
          </View>

          <Text style={styles.sectionTitle}>Status</Text>
          <View style={styles.chipRow}>
            {STATUSES.map((s) => (
              <FilterChip key={s} label={STATUS_LABELS[s!]} active={status === s} onPress={() => setStatus(s)} />
            ))}
          </View>

          <Button
            title={saving ? 'Saving…' : 'Save Changes'}
            onPress={handleSave}
            disabled={saving}
            loading={saving}
            style={{ marginTop: Spacing.lg }}
          />
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
  errorText: {
    fontSize: Typography.sm,
    color: Colors.error,
    textAlign: 'center',
    marginTop: Spacing.xl,
  },
  scroll: {
    padding: Spacing.lg,
    paddingBottom: Spacing['3xl'],
    gap: Spacing.sm,
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
  formCard: {
    borderRadius: Radius.xl,
    padding: Spacing.lg,
    gap: Spacing.md,
  },
  formDivider: {
    height: 1,
  },
  chipRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.xs,
  },
});

export default VehicleEditScreen;
