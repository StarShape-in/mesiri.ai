import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useTheme, useStyles } from '../../../src/theme';

interface ProjectAccessRowProps {
  projectName: string;
  isSelected: boolean;
  onToggle: () => void;
  siteAccessSummary: string; // e.g. "All Sites" or "3 of 7 Sites"
  onOpenSiteAccess: () => void;
  disabled?: boolean;
}

export function ProjectAccessRow({
  projectName,
  isSelected,
  onToggle,
  siteAccessSummary,
  onOpenSiteAccess,
  disabled = false,
}: ProjectAccessRowProps) {
  const { theme } = useTheme();
  const styles = useStyles(createStyles);

  return (
    <View style={[styles.container, disabled && styles.disabled]}>
      <TouchableOpacity 
        style={styles.checkboxContainer} 
        onPress={onToggle}
        disabled={disabled}
      >
        <View style={[styles.checkbox, isSelected && styles.checkboxSelected]}>
          {isSelected && <Ionicons name="checkmark" size={14} color="#FFF" />}
        </View>
      </TouchableOpacity>
      
      <TouchableOpacity 
        style={styles.contentContainer} 
        onPress={isSelected ? onOpenSiteAccess : onToggle}
        disabled={disabled}
      >
        <View style={styles.textContainer}>
          <Text style={styles.projectName}>{projectName}</Text>
          {isSelected && (
            <Text style={styles.siteAccess}>{siteAccessSummary}</Text>
          )}
        </View>
        {isSelected && (
          <Ionicons name="chevron-forward" size={20} color={theme.colors.textMuted} />
        )}
      </TouchableOpacity>
    </View>
  );
}

const createStyles = (theme: any) => StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: theme.spacing.space3,
    paddingHorizontal: theme.spacing.space4,
    backgroundColor: theme.colors.backgroundSurface,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.borderSubtle,
  },
  disabled: {
    opacity: 0.5,
  },
  checkboxContainer: {
    paddingRight: theme.spacing.space3,
    justifyContent: 'center',
  },
  checkbox: {
    width: 20,
    height: 20,
    borderRadius: theme.radius.xs,
    borderWidth: 2,
    borderColor: theme.colors.borderStrong,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: 'transparent',
  },
  checkboxSelected: {
    backgroundColor: theme.colors.actionPrimary,
    borderColor: theme.colors.actionPrimary,
  },
  contentContainer: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  textContainer: {
    flex: 1,
  },
  projectName: {
    fontSize: theme.typography.sizeMd,
    color: theme.colors.textPrimary,
    fontWeight: theme.typography.weightMedium,
  },
  siteAccess: {
    fontSize: theme.typography.sizeXs,
    color: theme.colors.textSecondary,
    marginTop: 2,
  },
});
