import React from 'react';
import { View, Text, StyleSheet, Pressable } from 'react-native';
import { Check } from 'lucide-react-native';
import { useTheme, useStyles } from '../../src/theme';
import { ThemeDefinition } from '../../src/theme/types';

export type ThemeOptionCardProps = {
  themeDef: ThemeDefinition;
  isSelected: boolean;
  onSelect: (id: string) => void;
};

export function ThemeOptionCard({ themeDef, isSelected, onSelect }: ThemeOptionCardProps) {
  const { theme } = useTheme();
  const styles = useStyles(createStyles);
  
  return (
    <Pressable
      onPress={() => onSelect(themeDef.id)}
      style={[styles.container, isSelected && styles.containerSelected]}
      accessibilityRole="radio"
      accessibilityState={{ checked: isSelected }}
      accessibilityLabel={`Select ${themeDef.name} theme`}
    >
      <View style={styles.header}>
        <Text style={styles.name}>{themeDef.name}</Text>
        {isSelected ? (
          <View style={styles.checkContainer}>
            <Check size={14} color={theme.colors.actionPrimaryForeground} strokeWidth={3} />
          </View>
        ) : (
          <View style={styles.uncheckContainer} />
        )}
      </View>
      
      {/* Visual Swatches */}
      <View style={styles.swatchContainer}>
        <View style={[styles.swatch, { backgroundColor: themeDef.preview.primary }]} />
        <View style={[styles.swatch, { backgroundColor: themeDef.preview.primaryStrong }]} />
        <View style={[styles.swatch, { backgroundColor: themeDef.preview.primaryBright }]} />
        <View style={[styles.swatch, { backgroundColor: themeDef.preview.surface }]} />
        <View style={[styles.swatch, { backgroundColor: themeDef.preview.foreground }]} />
      </View>
      
      <Text style={styles.description}>{themeDef.description}</Text>
    </Pressable>
  );
}

const createStyles = (theme: any) => StyleSheet.create({
  container: {
    backgroundColor: theme.colors.backgroundSurface,
    borderRadius: theme.radius.lg,
    borderWidth: 1,
    borderColor: theme.colors.borderSubtle,
    padding: 16,
    marginBottom: 12,
  },
  containerSelected: {
    borderColor: theme.colors.borderStrong,
    borderWidth: 2,
    padding: 15, // offset the 1px border growth to avoid layout shift
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  name: {
    fontSize: 16,
    fontWeight: theme.typography.weightBold,
    color: theme.colors.textPrimary,
  },
  checkContainer: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: theme.colors.actionPrimary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  uncheckContainer: {
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 2,
    borderColor: theme.colors.borderDefault,
  },
  swatchContainer: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 16,
  },
  swatch: {
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: theme.colors.borderSubtle,
  },
  description: {
    fontSize: 14,
    color: theme.colors.textMuted,
  }
});
