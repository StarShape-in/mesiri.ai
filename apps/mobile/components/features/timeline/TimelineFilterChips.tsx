import React from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable } from 'react-native';
import { useTheme, useStyles } from '../../../src/theme';
import { FILTER_CHIPS } from '../../../src/config/timelineCategories';

type TimelineFilterChipsProps = {
  activeKey: string;
  onChange: (key: string) => void;
};

export function TimelineFilterChips({ activeKey, onChange }: TimelineFilterChipsProps) {
  const { theme } = useTheme();
  const styles = useStyles(createStyles);

  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.container}
    >
      {FILTER_CHIPS.map((chip) => {
        const active = chip.key === activeKey;
        return (
          <Pressable
            key={chip.key}
            style={[styles.chip, active && styles.chipActive]}
            onPress={() => onChange(chip.key)}
          >
            <Text style={[styles.chipText, active && styles.chipTextActive]}>{chip.label}</Text>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

const createStyles = (theme: any) => StyleSheet.create({
  container: {
    paddingHorizontal: theme.spacing.space4,
    paddingVertical: theme.spacing.space3,
    gap: 10,
  },
  chip: {
    minHeight: 36,
    paddingHorizontal: theme.spacing.space4,
    paddingVertical: 9,
    justifyContent: 'center',
    borderRadius: theme.radius.full,
    borderWidth: 1,
    borderColor: theme.colors.borderDefault,
    backgroundColor: theme.colors.backgroundSurface,
  },
  chipActive: {
    backgroundColor: theme.colors.textPrimary,
    borderColor: theme.colors.textPrimary,
  },
  chipText: {
    fontSize: theme.typography.sizeSm,
    fontWeight: theme.typography.weightMedium,
    color: theme.colors.textSecondary,
  },
  chipTextActive: {
    color: theme.colors.backgroundSurface,
  },
});
