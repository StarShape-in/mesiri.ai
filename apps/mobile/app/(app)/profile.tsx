import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { Link } from 'expo-router';
import { useAuth } from '../_layout';
import { useEffect, useState } from 'react';
import { getToken } from '@mesiri/auth';
import { Ionicons } from '@expo/vector-icons';
import { useTheme, useStyles } from '../../src/theme';

export default function ProfileScreen() {
  const { signOut } = useAuth();
  const [userData, setUserData] = useState<{ sub?: string; org?: string; role?: string; name?: string; org_name?: string } | null>(null);
  const { theme } = useTheme();
  const styles = useStyles(createStyles);

  useEffect(() => {
    async function loadUser() {
      const token = await getToken();
      if (token && token.includes('.')) {
        try {
          // Decode JWT payload manually (Base64)
          const base64Url = token.split('.')[1];
          const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
          const jsonPayload = decodeURIComponent(
            atob(base64)
              .split('')
              .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
              .join('')
          );
          setUserData(JSON.parse(jsonPayload));
        } catch (e) {
          console.error('Failed to parse token', e);
        }
      }
    }
    loadUser();
  }, []);

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <View style={styles.avatar}>
          <Ionicons name="person" size={40} color={theme.colors.textInverse} />
        </View>
        <Text style={styles.name}>{userData?.name || 'Admin User'}</Text>
        <Text style={styles.role}>{userData?.role || 'User'}</Text>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Account Details</Text>
        
        <View style={styles.card}>
          <View style={[styles.row, { borderBottomWidth: 0 }]}>
            <Text style={styles.label}>Organization</Text>
            <Text style={styles.value} numberOfLines={1} ellipsizeMode="tail">
              {userData?.org_name || 'Loading...'}
            </Text>
          </View>
        </View>
      </View>

      {(userData?.role || '').toUpperCase() === 'ADMIN' && (
        <View style={styles.section}>
          <Link href="/users" asChild>
            <TouchableOpacity style={styles.manageTeamButton}>
              <Ionicons name="people-outline" size={20} color={theme.colors.actionPrimaryForeground} />
              <Text style={styles.manageTeamText}>Manage Team</Text>
            </TouchableOpacity>
          </Link>
        </View>
      )}

      <TouchableOpacity style={styles.signOutButton} onPress={signOut}>
        <Ionicons name="log-out-outline" size={20} color={theme.colors.statusDangerForeground} />
        <Text style={styles.signOutText}>Sign Out</Text>
      </TouchableOpacity>
    </View>
  );
}

const createStyles = (theme: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.backgroundApp,
    padding: theme.spacing.space6, // 24
  },
  header: {
    alignItems: 'center',
    marginBottom: theme.spacing.space8, // 32
    marginTop: theme.spacing.space4, // 16
  },
  avatar: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: theme.colors.backgroundInverse, // #1F222B approx
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: theme.spacing.space4,
    shadowColor: theme.shadow.action.shadowColor,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 12,
    elevation: 4,
  },
  name: {
    fontSize: theme.typography.size2xl, // 24
    fontWeight: theme.typography.weightBold,
    color: theme.colors.textPrimary,
    marginBottom: 4,
  },
  role: {
    fontSize: theme.typography.sizeSm,
    color: theme.colors.textSecondary,
    backgroundColor: theme.colors.backgroundSubtle,
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 12,
    overflow: 'hidden',
    fontWeight: theme.typography.weightMedium,
  },
  section: {
    marginBottom: theme.spacing.space8,
  },
  sectionTitle: {
    fontSize: theme.typography.sizeSm,
    fontWeight: theme.typography.weightSemiBold,
    color: theme.colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 12,
    paddingLeft: 4,
  },
  card: {
    backgroundColor: theme.colors.backgroundSurface,
    borderRadius: theme.radius.xl, // 16 is between lg/xl, let's say xl since we used it before for 16
    borderWidth: 1,
    borderColor: theme.colors.borderDefault,
    overflow: 'hidden',
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    padding: theme.spacing.space4,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.backgroundSubtle, // #F3F4F6
  },
  label: {
    fontSize: 15,
    color: theme.colors.textMuted,
    fontWeight: theme.typography.weightMedium,
  },
  value: {
    fontSize: 15,
    color: theme.colors.textPrimary,
    maxWidth: '50%',
    fontFamily: 'monospace',
  },
  manageTeamButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: theme.spacing.space2,
    padding: theme.spacing.space4,
    borderRadius: theme.radius.lg,
    backgroundColor: theme.colors.actionPrimary,
    borderWidth: 2,
    borderColor: theme.colors.borderStrong,
  },
  manageTeamText: {
    color: theme.colors.actionPrimaryForeground,
    fontSize: theme.typography.sizeMd,
    fontWeight: theme.typography.weightBold,
  },
  signOutButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: theme.spacing.space2,
    padding: theme.spacing.space4,
    borderRadius: theme.radius.lg,
    backgroundColor: theme.colors.statusDangerBackground,
    borderWidth: 1,
    borderColor: theme.colors.statusDangerBorder,
  },
  signOutText: {
    color: theme.colors.statusDangerForeground,
    fontSize: theme.typography.sizeMd,
    fontWeight: theme.typography.weightSemiBold,
  },
});
