import React from 'react';
import { View, Text, StyleSheet, Pressable } from 'react-native';
import { useStyles } from '../../../src/theme';

export type TimelineGranularity = 'day' | 'week' | 'month';

const OPTIONS: { key: TimelineGranularity; label: string }[] = [
  { key: 'day', label: 'Day' },
  { key: 'week', label: 'Week' },
  { key: 'month', label: 'Month' },
];

type TimelineGranularitySwitcherProps = {
  value: TimelineGranularity;
  onChange: (value: TimelineGranularity) => void;
};

export function TimelineGranularitySwitcher({ value, onChange }: TimelineGranularitySwitcherProps) {
  const styles = useStyles(createStyles);

  return (
    <View style={styles.container}>
      {OPTIONS.map((option) => {
        const active = option.key === value;
        return (
          <Pressable
            key={option.key}
            style={[styles.button, active && styles.buttonActive]}
            onPress={() => onChange(option.key)}
            accessibilityRole="tab"
            accessibilityState={{ selected: active }}
          >
            <Text style={[styles.buttonText, active && styles.buttonTextActive]}>{option.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const createStyles = (theme: any) => StyleSheet.create({
  container: {
    flexDirection: 'row',
    backgroundColor: theme.colors.backgroundSubtle,
    marginHorizontal: theme.spacing.space4,
    marginTop: theme.spacing.space3,
    borderRadius: theme.radius.lg,
    padding: 5,
  },
  button: {
    flex: 1,
    minHeight: 38,
    paddingVertical: 10,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: theme.radius.md,
  },
  buttonActive: {
    backgroundColor: theme.colors.backgroundSurface,
    ...theme.shadow.subtle,
  },
  buttonText: {
    fontSize: theme.typography.sizeSm,
    fontWeight: theme.typography.weightMedium,
    color: theme.colors.textMuted,
  },
  buttonTextActive: {
    color: theme.colors.textPrimary,
    fontWeight: theme.typography.weightSemiBold,
  },
});
