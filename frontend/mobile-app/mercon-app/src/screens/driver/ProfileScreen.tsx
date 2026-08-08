import React, { useState } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity,
  StyleSheet, SafeAreaView, StatusBar, ActivityIndicator,
} from 'react-native';
import { useRouter } from 'expo-router';
import {
  FileText, Truck, Settings, IdCard, CalendarClock, Phone, CalendarDays,
  Bell, Globe, ShieldCheck, Info, LifeBuoy, LogOut, ChevronRight,
  type LucideIcon,
} from 'lucide-react-native';
import { Colors, Spacing, Radius, Typography, Shadows } from '../../theme/tokens';
import { Avatar, Badge } from '../../components';
import { DriverBottomNav } from '../../navigation/DriverBottomNav';
import { useAuth } from '../../lib/auth-context';
import { useProfile } from '../../lib/use-profile';
import { initialsOf } from '../../lib/profile';

const SETTING_ROWS: { Icon: LucideIcon; label: string; value?: string; arrow?: boolean; route?: string }[] = [
  { Icon: Bell,        label: 'Notifications', route: '/notifications', arrow: true },
  { Icon: Globe,       label: 'Language', value: 'English', arrow: true },
  { Icon: ShieldCheck, label: 'Privacy Policy', arrow: true },
  { Icon: Info,        label: 'About MERCON', arrow: true },
  { Icon: LifeBuoy,    label: 'Help & Support', arrow: true },
];

function statusVariant(status: string): 'success' | 'warning' | 'info' | 'neutral' {
  switch (status) {
    case 'Available': return 'success';
    case 'OnTrip': return 'info';
    case 'Suspended': return 'warning';
    default: return 'neutral';
  }
}

function formatDate(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' });
}

const ProfileScreen = ({ navigation }: any) => {
  const [activeTab, setActiveTab] = useState('Profile');
  const router = useRouter();
  const { profile: authProfile, signOut } = useAuth();
  const { profile, loading, error } = useProfile();

  const name = profile?.name ?? authProfile?.name ?? 'Driver';
  const refId = profile?.ref_id ?? authProfile?.ref_id ?? '—';
  const status = profile?.status ?? authProfile?.status ?? '';

  const details: { Icon: LucideIcon; label: string; value: string }[] = profile
    ? [
        { Icon: IdCard, label: 'License No.', value: profile.license_number },
        { Icon: CalendarClock, label: 'License Expiry', value: formatDate(profile.license_expiry) },
        { Icon: Phone, label: 'Phone', value: profile.phone_primary ?? '—' },
        {
          Icon: Truck,
          label: 'Assigned Vehicle',
          value: profile.current_vehicle?.plate_number ?? 'None (no active trip)',
        },
        { Icon: CalendarDays, label: 'Member Since', value: formatDate(profile.createdAt) },
      ]
    : [];

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.gray100 }}>
      <StatusBar barStyle="dark-content" backgroundColor={Colors.white} />
      <ScrollView contentContainerStyle={styles.scroll}>
        {/* Profile Hero */}
        <View style={styles.hero}>
          <Avatar initials={initialsOf(name)} size={96} />
          <View style={styles.heroInfo}>
            <Text style={styles.name} numberOfLines={1}>{name}</Text>
            <View style={styles.heroTagsRow}>
              <Text style={styles.driverId}>{refId}</Text>
              {!!status && <Badge label={status} variant={statusVariant(status)} />}
            </View>
          </View>
        </View>

        {/* Quick Actions */}
        <View style={styles.quickActions}>
          {([
            { Icon: FileText, label: 'Documents', route: '/documents' },
            { Icon: Truck, label: 'Vehicle', route: '/vehicle' },
            { Icon: Settings, label: 'Settings', route: '/settings' },
          ] as { Icon: LucideIcon; label: string; route: string }[]).map((action) => (
            <TouchableOpacity
              key={action.label}
              style={styles.quickCard}
              activeOpacity={0.8}
              onPress={() => router.push(action.route as any)}
            >
              <action.Icon size={26} color={Colors.primary} strokeWidth={2} />
              <Text style={styles.quickLabel}>{action.label}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Driver Details */}
        <View style={styles.statsCard}>
          <Text style={styles.sectionTitle}>Driver Details</Text>
          {loading ? (
            <ActivityIndicator color={Colors.primary} />
          ) : error ? (
            <Text style={{ color: Colors.error, fontSize: Typography.sm }}>{error}</Text>
          ) : (
            details.map((row, i) => (
              <View
                key={row.label}
                style={[styles.settingRow, i < details.length - 1 ? styles.settingRowBorder : null]}
              >
                <View style={styles.settingLeft}>
                  <row.Icon size={20} color={Colors.gray500} strokeWidth={2} />
                  <Text style={styles.settingLabel}>{row.label}</Text>
                </View>
                <Text style={styles.settingValue}>{row.value}</Text>
              </View>
            ))
          )}
        </View>

        {/* Settings Rows */}
        <View style={styles.settingsCard}>
          {SETTING_ROWS.map((row, i) => (
            <TouchableOpacity
              key={row.label}
              style={[styles.settingRow, i < SETTING_ROWS.length - 1 ? styles.settingRowBorder : null]}
              activeOpacity={0.8}
              onPress={() => row.route && router.push(row.route as any)}
            >
              <View style={styles.settingLeft}>
                <row.Icon size={20} color={Colors.gray500} strokeWidth={2} />
                <Text style={styles.settingLabel}>{row.label}</Text>
              </View>
              <View style={styles.settingRight}>
                {row.value && <Text style={styles.settingValue}>{row.value}</Text>}
                {row.arrow && <ChevronRight size={18} color={Colors.gray400} strokeWidth={2} />}
              </View>
            </TouchableOpacity>
          ))}
        </View>

        {/* Logout */}
        <TouchableOpacity style={styles.logoutBtn} activeOpacity={0.8} onPress={() => signOut()}>
          <LogOut size={20} color={Colors.error} strokeWidth={2.2} />
          <Text style={styles.logoutText}>Logout</Text>
        </TouchableOpacity>

        <Text style={styles.version}>MERCON Driver App</Text>
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  scroll: {
    paddingBottom: 80,
  },
  hero: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.white,
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.xl,
    borderBottomWidth: 1,
    borderBottomColor: Colors.gray100,
    marginBottom: Spacing.lg,
    gap: Spacing.lg,
  },
  heroInfo: {
    flex: 1,
    gap: Spacing.xs,
  },
  name: {
    fontSize: Typography.xl,
    fontWeight: '800',
    color: Colors.gray900,
  },
  heroTagsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  driverId: {
    fontSize: Typography.sm,
    color: Colors.gray500,
  },
  quickActions: {
    flexDirection: 'row',
    paddingHorizontal: Spacing.lg,
    gap: Spacing.md,
    marginBottom: Spacing.lg,
  },
  quickCard: {
    flex: 1,
    backgroundColor: Colors.white,
    borderRadius: Radius.xl,
    padding: Spacing.md,
    alignItems: 'center',
    gap: Spacing.xs,
    ...Shadows.sm,
  },
  quickLabel: {
    fontSize: Typography.xs,
    color: Colors.gray600,
    fontWeight: '600',
  },
  statsCard: {
    backgroundColor: Colors.white,
    marginHorizontal: Spacing.lg,
    borderRadius: Radius.xl,
    padding: Spacing.lg,
    marginBottom: Spacing.lg,
    ...Shadows.sm,
  },
  sectionTitle: {
    fontSize: Typography.base,
    fontWeight: '700',
    color: Colors.gray900,
    marginBottom: Spacing.md,
  },
  settingsCard: {
    backgroundColor: Colors.white,
    marginHorizontal: Spacing.lg,
    borderRadius: Radius.xl,
    padding: Spacing.xs,
    marginBottom: Spacing.lg,
    ...Shadows.sm,
  },
  settingRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.md,
  },
  settingRowBorder: {
    borderBottomWidth: 1,
    borderBottomColor: Colors.gray100,
  },
  settingLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  settingLabel: {
    fontSize: Typography.sm,
    color: Colors.gray900,
    fontWeight: '500',
  },
  settingRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
  },
  settingValue: {
    fontSize: Typography.sm,
    color: Colors.gray500,
    flexShrink: 1,
    textAlign: 'right',
  },
  logoutBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.sm,
    backgroundColor: Colors.white,
    marginHorizontal: Spacing.lg,
    borderRadius: Radius.xl,
    padding: Spacing.lg,
    borderWidth: 1.5,
    borderColor: Colors.error,
    marginBottom: Spacing.lg,
  },
  logoutText: {
    fontSize: Typography.base,
    fontWeight: '700',
    color: Colors.error,
  },
  version: {
    textAlign: 'center',
    fontSize: Typography.xs,
    color: Colors.gray400,
    marginBottom: Spacing.xl,
  },
});

export default ProfileScreen;
