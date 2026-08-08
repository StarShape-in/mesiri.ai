import React, { useRef } from 'react';
import { StyleSheet, Pressable, Animated } from 'react-native';
import { Sparkles } from 'lucide-react-native';
import { useTheme, useStyles } from '../../src/theme';

export type MesiriAIButtonProps = {
  onPress: () => void;
};

export function MesiriAIButton({ onPress }: MesiriAIButtonProps) {
  const scale = useRef(new Animated.Value(1)).current;
  const { theme } = useTheme();
  const styles = useStyles(createStyles);

  const handlePressIn = () => {
    Animated.timing(scale, {
      toValue: 0.94,
      duration: 100,
      useNativeDriver: true,
    }).start();
  };

  const handlePressOut = () => {
    Animated.timing(scale, {
      toValue: 1,
      duration: 150,
      useNativeDriver: true,
    }).start();
  };

  return (
    <Pressable
      onPress={onPress}
      onPressIn={handlePressIn}
      onPressOut={handlePressOut}
      style={styles.container}
      accessibilityRole="button"
      aria-label="Open Mesiri AI"
    >
      <Animated.View style={[styles.button, { transform: [{ scale }] }]}>
        <Sparkles size={22} color={theme.components.aiButtonForeground} strokeWidth={2.5} fill={theme.components.aiButtonForeground} />
      </Animated.View>
    </Pressable>
  );
}

const createStyles = (theme: any) => StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  // Compact rounded-square signature action, contained within the nav bar.
  button: {
    width: 46,
    height: 46,
    borderRadius: theme.radius.lg, // 12
    backgroundColor: theme.components.aiButtonBackground,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: theme.components.aiButtonShadow,
    shadowOffset: theme.shadow.action.shadowOffset,
    shadowOpacity: theme.shadow.action.shadowOpacity,
    shadowRadius: theme.shadow.action.shadowRadius,
    elevation: theme.shadow.action.elevation,
  },
});
