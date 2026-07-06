import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useAuth } from '../_layout';
import { useScope } from '../../state/ScopeProvider';
import { PortfolioHomeScreen } from '../../components/screens/PortfolioHomeScreen';

export default function HomeScreen() {
  const { signOut } = useAuth();
  const { scope } = useScope();

  if (scope.mode === 'portfolio') {
    return <PortfolioHomeScreen />;
  }

  // Fallback for Project/Site modes until they are implemented
  return (
    <View style={styles.container}>
      <Text style={styles.title}>
        {scope.mode === 'project' ? 'Project Dashboard' : 'Site Dashboard'}
      </Text>
      <Text style={styles.subtitle}>
        {scope.mode === 'project' ? scope.projectName : `${scope.projectName} > ${scope.siteName}`}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#FAFAFB',
  },
  title: {
    fontSize: 20,
    fontWeight: '700',
    color: '#111111',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 14,
    color: '#737373',
  }
});
