import { View, Text, StyleSheet, TouchableOpacity, ScrollView } from 'react-native';
import { useAuth } from '../_layout';

export default function HomeScreen() {
  const { signOut } = useAuth();

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text style={styles.greeting}>Good morning,</Text>
        <Text style={styles.name}>Site Manager</Text>
      </View>

      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <Text style={styles.cardTitle}>WhatsApp Assistant</Text>
          <View style={styles.badge}>
            <Text style={styles.badgeText}>Active</Text>
          </View>
        </View>
        <Text style={styles.cardDescription}>
          Your WhatsApp number is linked to this account. You can now log site expenses and labor updates directly via WhatsApp.
        </Text>
      </View>
      
      <View style={styles.statsGrid}>
        <View style={styles.statBox}>
          <Text style={styles.statValue}>12</Text>
          <Text style={styles.statLabel}>Pending Approvals</Text>
        </View>
        <View style={styles.statBox}>
          <Text style={styles.statValue}>4</Text>
          <Text style={styles.statLabel}>Active Sites</Text>
        </View>
      </View>

      <TouchableOpacity style={styles.signOutButton} onPress={signOut}>
        <Text style={styles.signOutText}>Sign Out</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0F172A',
  },
  content: {
    padding: 24,
    gap: 24,
  },
  header: {
    marginBottom: 8,
  },
  greeting: {
    fontSize: 16,
    color: '#94A3B8',
    marginBottom: 4,
  },
  name: {
    fontSize: 28,
    fontWeight: '700',
    color: '#FFFFFF',
    letterSpacing: -0.5,
  },
  card: {
    backgroundColor: '#1E293B',
    borderRadius: 16,
    padding: 20,
    borderWidth: 1,
    borderColor: '#334155',
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#F8FAFC',
  },
  badge: {
    backgroundColor: 'rgba(16, 185, 129, 0.1)',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: 'rgba(16, 185, 129, 0.2)',
  },
  badgeText: {
    color: '#10B981',
    fontSize: 12,
    fontWeight: '600',
  },
  cardDescription: {
    fontSize: 14,
    color: '#94A3B8',
    lineHeight: 22,
  },
  statsGrid: {
    flexDirection: 'row',
    gap: 16,
  },
  statBox: {
    flex: 1,
    backgroundColor: '#1E293B',
    borderRadius: 16,
    padding: 20,
    borderWidth: 1,
    borderColor: '#334155',
    alignItems: 'center',
  },
  statValue: {
    fontSize: 32,
    fontWeight: '800',
    color: '#3B82F6',
    marginBottom: 4,
  },
  statLabel: {
    fontSize: 13,
    color: '#94A3B8',
    fontWeight: '500',
    textAlign: 'center',
  },
  signOutButton: {
    marginTop: 24,
    padding: 16,
    borderRadius: 12,
    backgroundColor: '#1E293B',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#334155',
  },
  signOutText: {
    color: '#EF4444',
    fontSize: 16,
    fontWeight: '600',
  }
});
