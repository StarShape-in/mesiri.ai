import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { LucideIcon } from 'lucide-react-native';

type EmptyStateProps = {
  message: string;
  Icon?: LucideIcon;
};

export function EmptyState({ message, Icon }: EmptyStateProps) {
  return (
    <View style={styles.container}>
      {Icon && <Icon size={24} color="#A3A3A3" strokeWidth={1.5} style={styles.icon} />}
      <Text style={styles.message}>{message}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 24,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FAFAFA',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: 'rgba(15,15,15,0.04)',
  },
  icon: {
    marginBottom: 8,
  },
  message: {
    fontSize: 14,
    color: '#737373',
    fontWeight: '500',
    textAlign: 'center',
  },
});
