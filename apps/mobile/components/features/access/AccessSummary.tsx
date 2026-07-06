import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useTheme, useStyles } from '../../../src/theme';

interface AccessSummaryProps {
  projectCount: number;
  siteCount: number;
  accessType: 'All Projects' | 'Custom Access';
}

export function AccessSummary({ projectCount, siteCount, accessType }: AccessSummaryProps) {
  const { theme } = useTheme();
  const styles = useStyles(createStyles);

  return (
    <View style={styles.container}>
      <View style={styles.metric}>
        <Text style={styles.label}>Projects Access</Text>
        <Text style={styles.value}>{projectCount} {projectCount === 1 ? 'Project' : 'Projects'}</Text>
      </View>
      <View style={styles.divider} />
      <View style={styles.metric}>
        <Text style={styles.label}>Sites Access</Text>
        <Text style={styles.value}>{siteCount} {siteCount === 1 ? 'Site' : 'Sites'}</Text>
      </View>
      <View style={styles.divider} />
      <View style={styles.metric}>
        <Text style={styles.label}>Access Type</Text>
        <Text style={styles.value}>{accessType}</Text>
      </View>
    </View>
  );
}

const createStyles = (theme: any) => StyleSheet.create({
  container: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    backgroundColor: theme.colors.backgroundSurface,
    borderRadius: theme.radius.md,
    padding: theme.spacing.space4,
    borderWidth: 1,
    borderColor: theme.colors.borderDefault,
  },
  metric: {
    flex: 1,
    alignItems: 'center',
    gap: theme.spacing.space1,
  },
  label: {
    fontSize: theme.typography.sizeXs,
    color: theme.colors.textMuted,
    fontWeight: theme.typography.weightMedium,
    textTransform: 'uppercase',
  },
  value: {
    fontSize: theme.typography.sizeMd,
    color: theme.colors.textPrimary,
    fontWeight: theme.typography.weightSemiBold,
  },
  divider: {
    width: 1,
    backgroundColor: theme.colors.borderSubtle,
    marginHorizontal: theme.spacing.space2,
  }
});
