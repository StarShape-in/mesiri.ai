import React from 'react';
import {
  TouchableOpacity, Text, View, ActivityIndicator,
  StyleSheet, ViewStyle, TextStyle,
} from 'react-native';
import { Colors, Spacing, Radius, Typography, Shadows } from '../theme/tokens';

type ButtonVariant = 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger' | 'success';
type ButtonSize    = 'sm' | 'md' | 'lg';

interface ButtonProps {
  /** Button text. `title` is accepted as an alias (the screens use it). */
  label?: string;
  title?: string;
  onPress?: () => void;
  variant?: ButtonVariant;
  size?: ButtonSize;
  disabled?: boolean;
  loading?: boolean;
  iconLeft?: React.ReactNode;
  iconRight?: React.ReactNode;
  fullWidth?: boolean;
  style?: ViewStyle;
}

export function Button({
  label, title, onPress, variant = 'primary', size = 'md',
  disabled, loading, iconLeft, iconRight, fullWidth, style,
}: ButtonProps) {
  const s = styles[variant];
  const sz = sizeStyles[size];
  const text = label ?? title ?? '';

  return (
    <TouchableOpacity
      onPress={onPress}
      disabled={disabled || loading}
      activeOpacity={0.82}
      style={[
        base.btn,
        sz.btn,
        s.btn,
        fullWidth && { width: '100%' },
        (disabled || loading) && base.disabled,
        variant === 'primary' && Shadows.primary,
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator size="small" color={variant === 'primary' || variant === 'danger' || variant === 'success' ? Colors.white : Colors.primary} />
      ) : (
        <>
          {iconLeft && <View style={base.iconLeft}>{iconLeft}</View>}
          <Text style={[sz.text, s.text]}>{text}</Text>
          {iconRight && <View style={base.iconRight}>{iconRight}</View>}
        </>
      )}
    </TouchableOpacity>
  );
}

const base = StyleSheet.create({
  btn:       { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', borderRadius: Radius.xl },
  disabled:  { opacity: 0.45 },
  iconLeft:  { marginRight: Spacing.sm },
  iconRight: { marginLeft: Spacing.sm },
});

const sizeStyles: Record<ButtonSize, { btn: ViewStyle; text: TextStyle }> = {
  sm: {
    btn:  { paddingHorizontal: Spacing.md, paddingVertical: Spacing.xs + 2 },
    text: { ...Typography.buttonSmall },
  },
  md: {
    btn:  { paddingHorizontal: Spacing.lg, paddingVertical: Spacing.md - 2 },
    text: { ...Typography.buttonMedium },
  },
  lg: {
    btn:  { paddingHorizontal: Spacing.xl, paddingVertical: Spacing.base - 1 },
    text: { ...Typography.buttonLarge },
  },
};

const styles: Record<ButtonVariant, { btn: ViewStyle; text: TextStyle }> = {
  primary: {
    btn:  { backgroundColor: Colors.primary },
    text: { color: Colors.white },
  },
  secondary: {
    btn:  { backgroundColor: Colors.gray100 },
    text: { color: Colors.dark },
  },
  outline: {
    btn:  { backgroundColor: 'transparent', borderWidth: 2, borderColor: Colors.primary },
    text: { color: Colors.primary },
  },
  ghost: {
    btn:  { backgroundColor: 'transparent' },
    text: { color: Colors.primary },
  },
  danger: {
    btn:  { backgroundColor: Colors.danger },
    text: { color: Colors.white },
  },
  success: {
    btn:  { backgroundColor: Colors.success },
    text: { color: Colors.white },
  },
};
