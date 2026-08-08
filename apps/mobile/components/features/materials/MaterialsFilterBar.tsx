import React from 'react';
import { View, TextInput, StyleSheet } from 'react-native';
import { useTheme, useStyles } from '../../../src/theme';
import { Search, Calendar } from 'lucide-react-native';

type MaterialsFilterBarProps = {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  dateFrom?: string;
  onDateFromChange: (date?: string) => void;
  dateTo?: string;
  onDateToChange: (date?: string) => void;
  showDateFilters: boolean;
};

export function MaterialsFilterBar({
  searchQuery,
  onSearchChange,
  dateFrom,
  onDateFromChange,
  dateTo,
  onDateToChange,
  showDateFilters,
}: MaterialsFilterBarProps) {
  const { theme } = useTheme();
  const styles = useStyles(createStyles);

  return (
    <View style={styles.container}>
      {/* Search Input */}
      <View style={styles.searchContainer}>
        <Search size={16} color={theme.colors.textMuted} style={styles.searchIcon} />
        <TextInput
          style={styles.searchInput}
          value={searchQuery}
          onChangeText={onSearchChange}
          placeholder="Search materials..."
          placeholderTextColor={theme.colors.textMuted}
        />
      </View>

      {/* Date Filters */}
      {showDateFilters && (
        <View style={styles.datesContainer}>
          <View style={styles.dateField}>
            <Calendar size={14} color={theme.colors.textMuted} style={styles.dateIcon} />
            <TextInput
              style={styles.dateInput}
              value={dateFrom || ''}
              onChangeText={(text) => onDateFromChange(text || undefined)}
              placeholder="From: YYYY-MM-DD"
              placeholderTextColor={theme.colors.textMuted}
            />
          </View>
          <View style={styles.dateField}>
            <Calendar size={14} color={theme.colors.textMuted} style={styles.dateIcon} />
            <TextInput
              style={styles.dateInput}
              value={dateTo || ''}
              onChangeText={(text) => onDateToChange(text || undefined)}
              placeholder="To: YYYY-MM-DD"
              placeholderTextColor={theme.colors.textMuted}
            />
          </View>
        </View>
      )}
    </View>
  );
}

const createStyles = (theme: any) => StyleSheet.create({
  container: {
    paddingHorizontal: theme.spacing.space4,
    paddingVertical: theme.spacing.space2,
    gap: 8,
  },
  searchContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: theme.colors.backgroundSurface,
    borderWidth: 1,
    borderColor: theme.colors.borderSubtle,
    borderRadius: theme.radius.md,
    paddingHorizontal: 12,
  },
  searchIcon: {
    marginRight: 8,
  },
  searchInput: {
    flex: 1,
    height: 40,
    fontSize: theme.typography.sizeSm,
    color: theme.colors.textPrimary,
  },
  datesContainer: {
    flexDirection: 'row',
    gap: 8,
  },
  dateField: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: theme.colors.backgroundSurface,
    borderWidth: 1,
    borderColor: theme.colors.borderSubtle,
    borderRadius: theme.radius.md,
    paddingHorizontal: 10,
  },
  dateIcon: {
    marginRight: 6,
  },
  dateInput: {
    flex: 1,
    height: 36,
    fontSize: 12,
    color: theme.colors.textPrimary,
  },
});
