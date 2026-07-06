import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useTheme, useStyles } from '../../../src/theme';
import { StatusBadge } from '../../ui/StatusBadge';

interface UserSummaryHeaderProps {
  name: string;
  role: string;
  email?: string;
  phone?: string;
  status: 'active' | 'inactive' | 'suspended' | 'invited';
}

export function UserSummaryHeader({ name, role, email, phone, status }: UserSummaryHeaderProps) {
  const { theme } = useTheme();
  const styles = useStyles(createStyles);

  const initial = name.charAt(0).toUpperCase();

  return (
    <View style={styles.container}>
      <View style={styles.avatar}>
        <Text style={styles.avatarText}>{initial}</Text>
      </View>
      <View style={styles.info}>
        <Text style={styles.name}>{name}</Text>
        <Text style={styles.contact}>{phone || email}</Text>
        <Text style={styles.role}>{role.replace('_', ' ')}</Text>
      </View>
      <View style={styles.statusContainer}>
        <StatusBadge status={status} />
      </View>
    </View>
  );
}

const createStyles = (theme: any) => StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: theme.spacing.space4,
    backgroundColor: theme.colors.backgroundSurface,
    borderRadius: theme.radius.lg,
    borderWidth: 1,
    borderColor: theme.colors.borderDefault,
    gap: theme.spacing.space4,
  },
  avatar: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: theme.colors.backgroundInverse,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 2,
    borderColor: theme.colors.borderStrong,
  },
  avatarText: {
    fontSize: theme.typography.sizeXl,
    fontWeight: theme.typography.weightBold,
    color: theme.colors.textInverse,
  },
  info: {
    flex: 1,
    gap: 2,
  },
  name: {
    fontSize: 18,
    fontWeight: theme.typography.weightSemiBold,
    color: theme.colors.textPrimary,
  },
  contact: {
    fontSize: theme.typography.sizeSm,
    color: theme.colors.textSecondary,
  },
  role: {
    fontSize: theme.typography.sizeSm,
    color: theme.colors.textMuted,
    textTransform: 'capitalize',
  },
  statusContainer: {
    alignSelf: 'flex-start',
  }
});
