import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { LucideIcon } from 'lucide-react-native';
import { useTheme, useStyles } from '../../src/theme';

type EmptyStateProps = {
  message: string;
  Icon?: LucideIcon;
};

export function EmptyState({ message, Icon }: EmptyStateProps) {
  const { theme } = useTheme();
  const styles = useStyles(createStyles);

  return (
    <View style={styles.container}>
      {Icon && <Icon size={26} color={theme.colors.textMuted} strokeWidth={1.5} style={styles.icon} />}
      <Text style={styles.message}>{message}</Text>
    </View>
  );
}

const createStyles = (theme: any) => StyleSheet.create({
  container: {
    padding: theme.spacing.space6,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: theme.colors.backgroundSubtle,
    borderRadius: theme.radius.lg,
    borderWidth: 1,
    borderColor: theme.colors.borderSubtle,
  },
  icon: {
    marginBottom: theme.spacing.space2,
  },
  message: {
    fontSize: theme.typography.sizeSm,
    color: theme.colors.textSecondary,
    fontWeight: theme.typography.weightMedium,
    textAlign: 'center',
  },
});
