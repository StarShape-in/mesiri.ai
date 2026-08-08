import React, { useState } from 'react';
import {
  View, TextInput, Text, TouchableOpacity,
  StyleSheet, ViewStyle, TextStyle, KeyboardTypeOptions, TextInputProps,
} from 'react-native';
import { Search } from 'lucide-react-native';
import { Colors, Spacing, Radius, Typography } from '../theme/tokens';

type InputState = 'default' | 'focused' | 'error' | 'success' | 'disabled';

interface InputProps {
  label?: string;
  value?: string;
  onChangeText?: (text: string) => void;
  placeholder?: string;
  state?: InputState;
  errorText?: string;
  successText?: string;
  iconLeft?: React.ReactNode;
  iconRight?: React.ReactNode;
  secureTextEntry?: boolean;
  keyboardType?: KeyboardTypeOptions;
  autoCapitalize?: TextInputProps['autoCapitalize'];
  autoCorrect?: boolean;
  multiline?: boolean;
  numberOfLines?: number;
  maxLength?: number;
  style?: ViewStyle;
}

export function Input({
  label, value, onChangeText, placeholder, state = 'default',
  errorText, successText, iconLeft, iconRight, secureTextEntry,
  keyboardType, autoCapitalize, autoCorrect, multiline, numberOfLines, maxLength, style,
}: InputProps) {
  const [focused, setFocused] = useState(false);
  const effectiveState = state === 'default' && focused ? 'focused' : state;
  const isDisabled = state === 'disabled';

  return (
    <View style={[styles.wrapper, style]}>
      {label && <Text style={styles.label}>{label}</Text>}
      <View style={[styles.container, stateStyles[effectiveState]]}>
        {iconLeft && <View style={styles.iconLeft}>{iconLeft}</View>}
        <TextInput
          style={[
            styles.input,
            multiline && styles.multiline,
            iconLeft ? { paddingLeft: 0 } : null,
          ]}
          value={value}
          onChangeText={onChangeText}
          placeholder={placeholder}
          placeholderTextColor={Colors.gray400}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          editable={!isDisabled}
          secureTextEntry={secureTextEntry}
          keyboardType={keyboardType}
          autoCapitalize={autoCapitalize}
          autoCorrect={autoCorrect}
          multiline={multiline}
          numberOfLines={numberOfLines}
          maxLength={maxLength}
        />
        {iconRight && <View style={styles.iconRight}>{iconRight}</View>}
      </View>
      {effectiveState === 'error' && errorText && (
        <Text style={styles.errorText}>{errorText}</Text>
      )}
      {effectiveState === 'success' && successText && (
        <Text style={styles.successText}>{successText}</Text>
      )}
    </View>
  );
}

/** Search input with magnifier icon slot */
export function SearchInput({
  value, onChangeText, placeholder = 'Search…', style,
}: { value?: string; onChangeText?: (t: string) => void; placeholder?: string; style?: ViewStyle }) {
  return (
    <View style={[searchStyles.wrapper, style]}>
      <View style={searchStyles.icon}>
        <Search size={18} color={Colors.gray400} strokeWidth={2} />
      </View>
      <TextInput
        style={searchStyles.input}
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={Colors.gray400}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper:     { gap: Spacing.xs - 2 },
  label:       { ...Typography.bodySmall, fontWeight: '600', color: Colors.dark },
  container:   {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: Spacing.base,
    borderRadius: Radius.xl,
    borderWidth: 2,
    borderColor: 'transparent',
    backgroundColor: Colors.gray100,
    minHeight: 48,
  },
  input:       { flex: 1, ...Typography.bodyMedium, color: Colors.dark, paddingVertical: Spacing.md - 2 },
  multiline:   { minHeight: 80, textAlignVertical: 'top', paddingTop: Spacing.md - 2 },
  iconLeft:    { marginRight: Spacing.sm },
  iconRight:   { marginLeft: Spacing.sm },
  errorText:   { ...Typography.caption, color: Colors.danger },
  successText: { ...Typography.caption, color: Colors.success },
});

const stateStyles: Record<InputState, ViewStyle> = {
  default:  {},
  focused:  { borderColor: `${Colors.primary}40` },
  error:    { backgroundColor: Colors.dangerLight, borderColor: `${Colors.danger}40` },
  success:  { backgroundColor: Colors.successLight, borderColor: `${Colors.success}40` },
  disabled: { opacity: 0.5 },
};

const searchStyles = StyleSheet.create({
  wrapper: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: Colors.gray100,
    borderRadius: Radius.xl,
    paddingHorizontal: Spacing.md,
    height: 44,
  },
  icon:  { marginRight: Spacing.sm },
  input: { flex: 1, ...Typography.bodyMedium, color: Colors.dark },
});
