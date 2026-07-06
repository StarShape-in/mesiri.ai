import React from 'react';
import { View, Text, StyleSheet, Pressable } from 'react-native';
import { Monitor, Sun, Moon } from 'lucide-react-native';
import { useTheme, useStyles } from '../../src/theme';
import { AppearanceMode } from '../../src/theme/types';

type AppearanceSelectorProps = {
  currentMode: AppearanceMode;
  onSelect: (mode: AppearanceMode) => void;
};

export function AppearanceSelector({ currentMode, onSelect }: AppearanceSelectorProps) {
  const { theme } = useTheme();
  const styles = useStyles(createStyles);
  
  const options: { id: AppearanceMode; label: string; icon: any }[] = [
    { id: 'system', label: 'System', icon: Monitor },
    { id: 'light', label: 'Light', icon: Sun },
    { id: 'dark', label: 'Dark', icon: Moon },
  ];
  
  return (
    <View style={styles.container}>
      {options.map((option, index) => {
        const isSelected = currentMode === option.id;
        const Icon = option.icon;
        
        return (
          <Pressable
            key={option.id}
            style={[
              styles.option,
              index === 0 && styles.firstOption,
              index === options.length - 1 && styles.lastOption,
              isSelected && styles.optionSelected
            ]}
            onPress={() => onSelect(option.id)}
            accessibilityRole="button"
            accessibilityState={{ selected: isSelected }}
          >
            <Icon 
              size={18} 
              color={isSelected ? theme.colors.actionPrimaryForeground : theme.colors.textMuted} 
            />
            <Text style={[styles.label, isSelected && styles.labelSelected]}>
              {option.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const createStyles = (theme: any) => StyleSheet.create({
  container: {
    flexDirection: 'row',
    borderRadius: theme.radius.md,
    borderWidth: 1,
    borderColor: theme.colors.borderSubtle,
    backgroundColor: theme.colors.backgroundSurface,
    overflow: 'hidden',
  },
  option: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    gap: 8,
    borderRightWidth: 1,
    borderRightColor: theme.colors.borderSubtle,
  },
  firstOption: {
    borderTopLeftRadius: theme.radius.md - 1,
    borderBottomLeftRadius: theme.radius.md - 1,
  },
  lastOption: {
    borderRightWidth: 0,
    borderTopRightRadius: theme.radius.md - 1,
    borderBottomRightRadius: theme.radius.md - 1,
  },
  optionSelected: {
    backgroundColor: theme.colors.actionPrimary,
  },
  label: {
    fontSize: 14,
    fontWeight: theme.typography.weightSemiBold,
    color: theme.colors.textPrimary,
  },
  labelSelected: {
    color: theme.colors.actionPrimaryForeground,
  }
});
