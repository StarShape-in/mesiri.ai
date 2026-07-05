import { View, Text, StyleSheet } from 'react-native';

export default function SitesScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Sites</Text>
      <Text style={styles.subtitle}>Active projects and locations will appear here.</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#FAFAFB',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
  title: {
    fontSize: 24,
    fontWeight: '600',
    color: '#0E1116',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 16,
    color: '#687280',
    textAlign: 'center',
  },
});
