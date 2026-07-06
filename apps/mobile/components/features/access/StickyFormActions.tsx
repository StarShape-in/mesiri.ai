import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ActivityIndicator } from 'react-native';
import { useTheme, useStyles } from '../../../src/theme';

interface StickyFormActionsProps {
  visible: boolean;
  onDiscard: () => void;
  onSave: () => void;
  isSaving?: boolean;
}

export function StickyFormActions({ visible, onDiscard, onSave, isSaving = false }: StickyFormActionsProps) {
  const { theme } = useTheme();
  const styles = useStyles(createStyles);

  if (!visible) return null;

  return (
    <View style={styles.container}>
      <Text style={styles.warningText}>Unsaved access changes</Text>
      <View style={styles.actions}>
        <TouchableOpacity style={styles.discardButton} onPress={onDiscard} disabled={isSaving}>
          <Text style={styles.discardText}>Discard</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.saveButton} onPress={onSave} disabled={isSaving}>
          {isSaving ? (
            <ActivityIndicator color={theme.colors.actionPrimaryForeground} size="small" />
          ) : (
            <Text style={styles.saveText}>Save Changes</Text>
          )}
        </TouchableOpacity>
      </View>
    </View>
  );
}

const createStyles = (theme: any) => StyleSheet.create({
  container: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: theme.colors.backgroundSurface,
    padding: theme.spacing.space4,
    paddingBottom: 32, // Safe area approx
    borderTopWidth: 1,
    borderTopColor: theme.colors.borderDefault,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -4 },
    shadowOpacity: 0.05,
    shadowRadius: 10,
    elevation: 10,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  warningText: {
    fontSize: theme.typography.sizeSm,
    fontWeight: theme.typography.weightMedium,
    color: '#F59E0B', // warning color for unsaved
  },
  actions: {
    flexDirection: 'row',
    gap: theme.spacing.space3,
  },
  discardButton: {
    paddingVertical: theme.spacing.space2,
    paddingHorizontal: theme.spacing.space3,
    borderRadius: theme.radius.md,
  },
  discardText: {
    color: theme.colors.textSecondary,
    fontWeight: theme.typography.weightMedium,
  },
  saveButton: {
    backgroundColor: theme.colors.actionPrimary,
    paddingVertical: theme.spacing.space2,
    paddingHorizontal: theme.spacing.space4,
    borderRadius: theme.radius.md,
    minWidth: 120,
    alignItems: 'center',
  },
  saveText: {
    color: theme.colors.actionPrimaryForeground,
    fontWeight: theme.typography.weightSemiBold,
  }
});
