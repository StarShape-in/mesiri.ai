import React from 'react';
import { View, Text, ScrollView, TouchableOpacity, StyleSheet, SafeAreaView, StatusBar, Alert } from 'react-native';
import { useRouter } from 'expo-router';
import {
  Users, Truck, FileText, CalendarClock, User, LogOut, ChevronRight, type LucideIcon,
} from 'lucide-react-native';
import { Colors, Spacing, Radius, Typography, Shadows } from '../../theme/tokens';
import { useAuth } from '../../lib/auth-context';

const OPERATIONS_ROWS: { Icon: LucideIcon; label: string; desc: string; route: string }[] = [
  { Icon: Truck, label: 'Fleet', desc: 'View and edit vehicles', route: '/operator/vehicles' },
  { Icon: FileText, label: 'Invoices', desc: 'View invoices and record payments', route: '/operator/invoices' },
  { Icon: Users, label: 'Customers', desc: 'View, add and edit customers', route: '/operator/customers' },
  { Icon: CalendarClock, label: 'Vehicle Renewals', desc: 'Documents expiring soon', route: '/operator/vehicle-renewals' },
];

const MoreScreen = () => {
  const router = useRouter();
  const { profile, signOut } = useAuth();

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.gray100 }}>
      <StatusBar barStyle="dark-content" backgroundColor={Colors.white} />
      <View style={styles.header}>
        <Text style={styles.headerTitle}>More</Text>
      </View>

      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.profileCard}>
          <View style={styles.avatarBox}>
            <User size={22} color={Colors.white} strokeWidth={2} />
          </View>
          <View>
            <Text style={styles.profileName}>{profile?.name ?? 'Operator'}</Text>
            <Text style={styles.profileRole}>Operator</Text>
          </View>
        </View>

        <Text style={styles.groupLabel}>Operations</Text>
        <View style={styles.groupCard}>
          {OPERATIONS_ROWS.map((row, i) => (
            <TouchableOpacity
              key={row.label}
              style={[styles.row, i < OPERATIONS_ROWS.length - 1 ? styles.rowBorder : null]}
              activeOpacity={0.8}
              onPress={() => router.push(row.route as any)}
            >
              <View style={styles.rowIconBox}>
                <row.Icon size={18} color={Colors.gray600} strokeWidth={2} />
              </View>
              <View style={styles.rowContent}>
                <Text style={styles.rowLabel}>{row.label}</Text>
                <Text style={styles.rowDesc}>{row.desc}</Text>
              </View>
              <ChevronRight size={18} color={Colors.gray400} strokeWidth={2} />
            </TouchableOpacity>
          ))}
        </View>

        <TouchableOpacity
          style={styles.logoutBtn}
          activeOpacity={0.8}
          onPress={() => Alert.alert('Sign Out', 'Are you sure you want to sign out?', [
            { text: 'Cancel', style: 'cancel' },
            { text: 'Sign Out', style: 'destructive', onPress: () => signOut() },
          ])}
        >
          <LogOut size={20} color={Colors.error} strokeWidth={2.2} />
          <Text style={styles.logoutText}>Sign Out</Text>
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  header: {
    backgroundColor: Colors.white,
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: Colors.gray100,
  },
  headerTitle: {
    fontSize: Typography.xl,
    fontWeight: '800',
    color: Colors.gray900,
  },
  scroll: {
    padding: Spacing.lg,
    paddingBottom: 100,
    gap: Spacing.xs,
  },
  profileCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    backgroundColor: Colors.white,
    borderRadius: Radius.xl,
    padding: Spacing.lg,
    marginBottom: Spacing.md,
    ...Shadows.sm,
  },
  avatarBox: {
    width: 48,
    height: 48,
    borderRadius: Radius.lg,
    backgroundColor: Colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  profileName: {
    fontSize: Typography.base,
    fontWeight: '700',
    color: Colors.gray900,
  },
  profileRole: {
    fontSize: Typography.xs,
    color: Colors.primary,
    fontWeight: '600',
    marginTop: 1,
  },
  groupLabel: {
    fontSize: Typography.xs,
    color: Colors.gray500,
    fontWeight: '700',
    letterSpacing: 1,
    textTransform: 'uppercase',
    marginTop: Spacing.md,
    marginBottom: Spacing.xs,
    paddingHorizontal: Spacing.xs,
  },
  groupCard: {
    backgroundColor: Colors.white,
    borderRadius: Radius.xl,
    overflow: 'hidden',
    ...Shadows.sm,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    gap: Spacing.md,
  },
  rowBorder: {
    borderBottomWidth: 1,
    borderBottomColor: Colors.gray100,
  },
  rowIconBox: {
    width: 36,
    height: 36,
    borderRadius: Radius.lg,
    backgroundColor: Colors.gray100,
    alignItems: 'center',
    justifyContent: 'center',
  },
  rowContent: {
    flex: 1,
  },
  rowLabel: {
    fontSize: Typography.sm,
    fontWeight: '600',
    color: Colors.gray900,
  },
  rowDesc: {
    fontSize: Typography.xs,
    color: Colors.gray500,
    marginTop: 1,
  },
  logoutBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.sm,
    backgroundColor: Colors.white,
    borderRadius: Radius.xl,
    padding: Spacing.lg,
    borderWidth: 1.5,
    borderColor: Colors.error,
    marginTop: Spacing.lg,
  },
  logoutText: {
    fontSize: Typography.base,
    fontWeight: '700',
    color: Colors.error,
  },
});

export default MoreScreen;
