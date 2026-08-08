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
  operatorService, invalidateOperatorDrivers, useOperatorDriverById,
  type UpdateDriverInput,
} from '../../lib/operator';

const STATUSES: UpdateDriverInput['status'][] = ['Available', 'OnTrip', 'OffDuty', 'Inactive'];
const STATUS_LABELS: Record<string, string> = {
  Available: 'Available',
  OnTrip: 'On Trip',
  OffDuty: 'Off Duty',
  Inactive: 'Inactive',
};

function toDDMMYYYY(iso?: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()}`;
}

function parseDDMMYYYY(value: string): string | undefined {
  const match = value.trim().match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (!match) return undefined;
  const [, dd, mm, yyyy] = match;
  const d = new Date(Number(yyyy), Number(mm) - 1, Number(dd));
  return Number.isNaN(d.getTime()) ? undefined : d.toISOString();
}

const DriverEditScreen = () => {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { driver, loading, error } = useOperatorDriverById(id);

  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [phone, setPhone] = useState('');
  const [licenseNumber, setLicenseNumber] = useState('');
  const [licenseExpiry, setLicenseExpiry] = useState('');
  const [status, setStatus] = useState<UpdateDriverInput['status']>('Available');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!driver) return;
    setFirstName(driver.first_name);
    setLastName(driver.last_name);
    setPhone(driver.phone_primary ?? '');
    setLicenseNumber(driver.license_number);
    setLicenseExpiry(toDDMMYYYY(driver.license_expiry));
    setStatus((driver.status as UpdateDriverInput['status']) ?? 'Available');
  }, [driver]);

  const handleSave = async () => {
    if (!id || saving) return;
    setSaving(true);
    try {
      const payload: UpdateDriverInput = {
        first_name: firstName.trim() || undefined,
        last_name: lastName.trim() || undefined,
        phone_primary: phone.trim() || undefined,
        license_number: licenseNumber.trim() || undefined,
        license_expiry: parseDDMMYYYY(licenseExpiry),
        status,
      };
      await operatorService.updateDriver(id, payload);
      invalidateOperatorDrivers();
      router.back();
    } catch (e) {
      Alert.alert('Could not save driver', getApiErrorMessage(e));
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
        <Text style={styles.headerTitle}>Edit Driver</Text>
        <View style={styles.placeholder} />
      </View>

      {loading && !driver ? (
        <ActivityIndicator color={Colors.primary} style={{ marginTop: Spacing['3xl'] }} />
      ) : !driver ? (
        <Text style={styles.errorText}>{error ?? 'Driver not found'}</Text>
      ) : (
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          <Text style={styles.sectionTitle}>Name</Text>
          <Card style={styles.formCard}>
            <View style={styles.rowFields}>
              <Input style={{ flex: 1 }} label="First Name" value={firstName} onChangeText={setFirstName} />
              <Input style={{ flex: 1 }} label="Last Name" value={lastName} onChangeText={setLastName} />
            </View>
          </Card>

          <Text style={styles.sectionTitle}>Contact & License</Text>
          <Card style={styles.formCard}>
            <Input label="Phone" value={phone} onChangeText={setPhone} keyboardType="phone-pad" />
            <View style={styles.formDivider} />
            <Input label="License Number" value={licenseNumber} onChangeText={setLicenseNumber} />
            <View style={styles.formDivider} />
            <Input label="License Expiry" value={licenseExpiry} onChangeText={setLicenseExpiry} placeholder="DD/MM/YYYY" keyboardType="numeric" />
          </Card>

          <Text style={styles.sectionTitle}>Status</Text>
          <View style={styles.statusRow}>
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
  rowFields: {
    flexDirection: 'row',
    gap: Spacing.lg,
  },
  statusRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.xs,
  },
});

export default DriverEditScreen;
