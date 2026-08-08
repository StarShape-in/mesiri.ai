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
  operatorService, invalidateOperatorCustomers, useOperatorCustomerById,
} from '../../lib/operator';

const CustomerEditScreen = () => {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id?: string }>();
  const isEditing = !!id;
  const { customer, loading, error } = useOperatorCustomerById(id);

  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [creditLimit, setCreditLimit] = useState('');
  const [isActive, setIsActive] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!customer) return;
    setName(customer.name);
    setPhone(customer.contact_phone ?? '');
    setCreditLimit(String(customer.credit_limit ?? 0));
    setIsActive(customer.isActive ?? true);
  }, [customer]);

  const isValid = name.trim().length > 0 && phone.trim().length > 0;

  const handleSave = async () => {
    if (!isValid || saving) return;
    setSaving(true);
    try {
      const creditNum = parseFloat(creditLimit);
      if (isEditing && id) {
        await operatorService.updateCustomer(id, {
          name: name.trim(),
          contact_phone: phone.trim(),
          credit_limit: Number.isFinite(creditNum) ? creditNum : undefined,
          isActive,
        });
      } else {
        await operatorService.createCustomer({
          name: name.trim(),
          contact_phone: phone.trim(),
          credit_limit: Number.isFinite(creditNum) ? creditNum : undefined,
        });
      }
      invalidateOperatorCustomers();
      router.back();
    } catch (e) {
      Alert.alert(`Could not ${isEditing ? 'save' : 'create'} customer`, getApiErrorMessage(e));
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
        <Text style={styles.headerTitle}>{isEditing ? 'Edit Customer' : 'New Customer'}</Text>
        <View style={styles.placeholder} />
      </View>

      {isEditing && loading && !customer ? (
        <ActivityIndicator color={Colors.primary} style={{ marginTop: Spacing['3xl'] }} />
      ) : isEditing && !customer ? (
        <Text style={styles.errorText}>{error ?? 'Customer not found'}</Text>
      ) : (
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          <Text style={styles.sectionTitle}>Details</Text>
          <Card style={styles.formCard}>
            <Input label="Customer Name" value={name} onChangeText={setName} placeholder="e.g. Almarai Fresh Distribution" />
            <View style={styles.formDivider} />
            <Input label="Contact Phone" value={phone} onChangeText={setPhone} placeholder="+9665XXXXXXXX" keyboardType="phone-pad" />
            <View style={styles.formDivider} />
            <Input label="Credit Limit (SAR)" value={creditLimit} onChangeText={setCreditLimit} placeholder="0" keyboardType="numeric" />
          </Card>

          {isEditing && (
            <>
              <Text style={styles.sectionTitle}>Status</Text>
              <View style={styles.chipRow}>
                <FilterChip label="Active" active={isActive} onPress={() => setIsActive(true)} />
                <FilterChip label="Inactive" active={!isActive} onPress={() => setIsActive(false)} />
              </View>
            </>
          )}

          <Button
            title={saving ? 'Saving…' : isEditing ? 'Save Changes' : 'Create Customer'}
            onPress={handleSave}
            disabled={!isValid || saving}
            loading={saving}
            style={{ marginTop: Spacing.lg }}
          />

          {!isValid && (
            <Text style={styles.validationHint}>Fill in customer name and contact phone to continue.</Text>
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
    gap: Spacing.xs,
  },
  validationHint: {
    fontSize: Typography.xs,
    color: Colors.gray400,
    textAlign: 'center',
    marginTop: Spacing.xs,
  },
});

export default CustomerEditScreen;
