import { View, Text, StyleSheet } from 'react-native';

export default function TimelineScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Timeline</Text>
      <Text style={styles.subtitle}>Project updates and milestones.</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FAFAFB', alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 24, fontWeight: '600', color: '#0E1116', marginBottom: 8 },
  subtitle: { fontSize: 16, color: '#687280' },
});
