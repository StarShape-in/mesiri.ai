import React from 'react';
import { Text, TextStyle, StyleSheet } from 'react-native';
import { Colors, Typography as T } from '../theme/tokens';

type TextColor = 'primary' | 'secondary' | 'muted' | 'brand' | 'danger' | 'success' | 'warning' | 'white';

const colorMap: Record<TextColor, string> = {
  primary:   Colors.dark,
  secondary: Colors.gray700,
  muted:     Colors.gray500,
  brand:     Colors.primary,
  danger:    Colors.danger,
  success:   Colors.success,
  warning:   Colors.warning,
  white:     Colors.white,
};

interface TypoProps {
  children: React.ReactNode;
  color?: TextColor;
  style?: TextStyle;
  numberOfLines?: number;
}

export const Heading  = ({ children, color = 'primary', style, ...p }: TypoProps) => (
  <Text style={[T.headingL, { color: colorMap[color] }, style]} {...p}>{children}</Text>
);
export const Title    = ({ children, color = 'primary', style, ...p }: TypoProps) => (
  <Text style={[T.headingS, { color: colorMap[color] }, style]} {...p}>{children}</Text>
);
export const Body     = ({ children, color = 'primary', style, ...p }: TypoProps) => (
  <Text style={[T.bodyMedium, { color: colorMap[color] }, style]} {...p}>{children}</Text>
);
export const Caption  = ({ children, color = 'muted', style, ...p }: TypoProps) => (
  <Text style={[T.caption, { color: colorMap[color] }, style]} {...p}>{children}</Text>
);
export const Overline = ({ children, color = 'muted', style, ...p }: TypoProps) => (
  <Text style={[T.overline, { color: colorMap[color], textTransform: 'uppercase' }, style]} {...p}>{children}</Text>
);
export const Mono     = ({ children, color = 'brand', style, ...p }: TypoProps) => (
  <Text style={[T.mono, { color: colorMap[color] }, style]} {...p}>{children}</Text>
);
