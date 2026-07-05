import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { useAuth } from '../_layout';
import { useEffect, useState } from 'react';
import { getToken } from '@mesiri/auth';
import { Ionicons } from '@expo/vector-icons';

export default function ProfileScreen() {
  const { signOut } = useAuth();
  const [userData, setUserData] = useState<{ sub?: string; org?: string; role?: string; name?: string; org_name?: string } | null>(null);

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
          <Ionicons name="person" size={40} color="#FFFFFF" />
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

      <TouchableOpacity style={styles.signOutButton} onPress={signOut}>
        <Ionicons name="log-out-outline" size={20} color="#EF4444" />
        <Text style={styles.signOutText}>Sign Out</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#FAFAFB',
    padding: 24,
  },
  header: {
    alignItems: 'center',
    marginBottom: 32,
    marginTop: 16,
  },
  avatar: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: '#1F222B',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 12,
    elevation: 4,
  },
  name: {
    fontSize: 24,
    fontWeight: '700',
    color: '#0E1116',
    marginBottom: 4,
  },
  role: {
    fontSize: 14,
    color: '#687280',
    backgroundColor: '#F3F4F6',
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 12,
    overflow: 'hidden',
    fontWeight: '500',
  },
  section: {
    marginBottom: 32,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#687280',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 12,
    paddingLeft: 4,
  },
  card: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#E5E7EB',
    overflow: 'hidden',
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#F3F4F6',
  },
  label: {
    fontSize: 15,
    color: '#485563',
    fontWeight: '500',
  },
  value: {
    fontSize: 15,
    color: '#0E1116',
    maxWidth: '50%',
    fontFamily: 'monospace',
  },
  signOutButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    padding: 16,
    borderRadius: 12,
    backgroundColor: '#FEE2E2',
    borderWidth: 1,
    borderColor: '#FECACA',
  },
  signOutText: {
    color: '#EF4444',
    fontSize: 16,
    fontWeight: '600',
  },
});
