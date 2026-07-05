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

      {/* Dark Component for high-emphasis intelligence/status */}
      <View style={styles.darkCard}>
        <View style={styles.cardHeader}>
          <Text style={styles.darkCardTitle}>WhatsApp Assistant</Text>
          <View style={styles.badgeSuccess}>
            <Text style={styles.badgeSuccessText}>Active</Text>
          </View>
        </View>
        <Text style={styles.darkCardDescription}>
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
    backgroundColor: '#FAFAFB', // surface-app
  },
  content: {
    padding: 20, // mobile page padding (16-20px)
    paddingTop: 48,
    gap: 24, // section gap
  },
  header: {
    marginBottom: 8,
  },
  greeting: {
    fontSize: 16,
    color: '#687280', // neutral-500
    marginBottom: 4,
  },
  name: {
    fontSize: 28,
    fontWeight: '700',
    color: '#0E1116', // neutral-900
    letterSpacing: -0.5,
  },
  darkCard: {
    backgroundColor: '#0E1116', // dark-component-bg
    borderRadius: 16, // card radius
    padding: 20,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.10)',
    shadowColor: '#101828',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.08,
    shadowRadius: 12,
    elevation: 3,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  darkCardTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  badgeSuccess: {
    backgroundColor: '#DCFCE7', // success-soft
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  badgeSuccessText: {
    color: '#22C55E', // success
    fontSize: 12,
    fontWeight: '600',
  },
  darkCardDescription: {
    fontSize: 14,
    color: '#D1D5DB', // dark-component-text-secondary
    lineHeight: 22,
  },
  statsGrid: {
    flexDirection: 'row',
    gap: 16,
  },
  statBox: {
    flex: 1,
    backgroundColor: '#FFFFFF', // surface-primary
    borderRadius: 16,
    padding: 20,
    borderWidth: 1,
    borderColor: '#E5E7EB', // border-default
    alignItems: 'center',
    shadowColor: '#101828',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 4,
    elevation: 2,
  },
  statValue: {
    fontSize: 32,
    fontWeight: '700',
    color: '#0E1116', // neutral-900
    marginBottom: 4,
  },
  statLabel: {
    fontSize: 13,
    color: '#687280', // neutral-500
    fontWeight: '500',
    textAlign: 'center',
  },
  signOutButton: {
    marginTop: 24,
    padding: 16,
    borderRadius: 12,
    backgroundColor: '#FFFFFF', // btn-secondary
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#D1D5DB', // btn-secondary border
  },
  signOutText: {
    color: '#EF4444', // destructive color
    fontSize: 16,
    fontWeight: '600',
  }
});
