import { View, Text, StyleSheet } from 'react-native';

export default function FieldScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Field Operations</Text>
      <Text style={styles.subtitle}>On-site logs, labor, and machinery.</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FAFAFB', alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 24, fontWeight: '600', color: '#0E1116', marginBottom: 8 },
  subtitle: { fontSize: 16, color: '#687280' },
});
