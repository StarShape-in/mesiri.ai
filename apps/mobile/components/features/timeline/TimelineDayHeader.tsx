import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useStyles } from '../../../src/theme';

type TimelineDayHeaderProps = {
  label: string;
  dateText: string;
  summaryText: string;
};

export function TimelineDayHeader({ label, dateText, summaryText }: TimelineDayHeaderProps) {
  const styles = useStyles(createStyles);

  return (
    <View style={styles.container}>
      <View style={styles.titleRow}>
        <Text style={styles.label}>{label}</Text>
        <Text style={styles.dateText}>{dateText}</Text>
      </View>
      {summaryText ? <Text style={styles.summary}>{summaryText}</Text> : null}
    </View>
  );
}

const createStyles = (theme: any) => StyleSheet.create({
  container: {
    backgroundColor: theme.colors.backgroundApp,
    paddingTop: theme.spacing.space3,
    paddingBottom: theme.spacing.space2,
  },
  titleRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: 8,
  },
  label: {
    fontSize: theme.typography.sizeSm,
    fontWeight: theme.typography.weightSemiBold,
    color: theme.colors.textPrimary,
  },
  dateText: {
    fontSize: 12,
    color: theme.colors.textMuted,
  },
  summary: {
    fontSize: 12,
    color: theme.colors.textSecondary,
    marginTop: 2,
  },
});
