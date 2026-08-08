import React from 'react';
import { Modal, View, Text, StyleSheet, TouchableOpacity, ActivityIndicator } from 'react-native';
import { useTheme, useStyles } from '../../src/theme';

interface ConfirmationDialogProps {
  visible: boolean;
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  isDestructive?: boolean;
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmationDialog({
  visible,
  title,
  message,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  isDestructive = false,
  loading = false,
  onConfirm,
  onCancel
}: ConfirmationDialogProps) {
  const { theme } = useTheme();
  const styles = useStyles(createStyles);

  return (
    <Modal visible={visible} animationType="fade" transparent={true} onRequestClose={onCancel}>
      <View style={styles.overlay}>
        <View style={styles.dialog}>
          <Text style={styles.title}>{title}</Text>
          <Text style={styles.message}>{message}</Text>
          
          <View style={styles.actions}>
            <TouchableOpacity style={styles.cancelButton} onPress={onCancel} disabled={loading}>
              <Text style={styles.cancelText}>{cancelText}</Text>
            </TouchableOpacity>
            <TouchableOpacity 
              style={[styles.confirmButton, isDestructive && styles.destructiveButton]} 
              onPress={onConfirm}
              disabled={loading}
            >
              {loading ? (
                <ActivityIndicator color={isDestructive ? '#FFF' : theme.colors.actionPrimaryForeground} size="small" />
              ) : (
                <Text style={[styles.confirmText, isDestructive && styles.destructiveText]}>{confirmText}</Text>
              )}
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const createStyles = (theme: any) => StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: theme.spacing.space4,
  },
  dialog: {
    width: '100%',
    maxWidth: 400,
    backgroundColor: theme.colors.backgroundSurface,
    borderRadius: theme.radius.xl,
    padding: theme.spacing.space6,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.1,
    shadowRadius: 20,
    elevation: 10,
  },
  title: {
    fontSize: theme.typography.sizeXl,
    fontWeight: theme.typography.weightSemiBold,
    color: theme.colors.textPrimary,
    marginBottom: theme.spacing.space3,
  },
  message: {
    fontSize: theme.typography.sizeMd,
    color: theme.colors.textSecondary,
    lineHeight: 22,
    marginBottom: theme.spacing.space6,
  },
  actions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: theme.spacing.space3,
  },
  cancelButton: {
    paddingVertical: theme.spacing.space3,
    paddingHorizontal: theme.spacing.space4,
    borderRadius: theme.radius.md,
    backgroundColor: theme.colors.backgroundSubtle,
  },
  cancelText: {
    fontSize: theme.typography.sizeMd,
    fontWeight: theme.typography.weightMedium,
    color: theme.colors.textSecondary,
  },
  confirmButton: {
    paddingVertical: theme.spacing.space3,
    paddingHorizontal: theme.spacing.space4,
    borderRadius: theme.radius.md,
    backgroundColor: theme.colors.actionPrimary,
    minWidth: 100,
    alignItems: 'center',
  },
  confirmText: {
    fontSize: theme.typography.sizeMd,
    fontWeight: theme.typography.weightMedium,
    color: theme.colors.actionPrimaryForeground,
  },
  destructiveButton: {
    backgroundColor: '#EF4444', // Tailwind red-500 for error
  },
  destructiveText: {
    color: '#FFFFFF',
  }
});
