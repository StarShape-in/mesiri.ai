import React, { useRef } from 'react';
import { View, Text, StyleSheet, Pressable, Image, Animated } from 'react-native';
import { UserRound } from 'lucide-react-native';
import { useTheme, useStyles } from '../../src/theme';

export type MesiriProfileAvatarProps = {
  user?: {
    name?: string;
    avatarUrl?: string;
  };
  onPress: () => void;
};

export function MesiriProfileAvatar({ user, onPress }: MesiriProfileAvatarProps) {
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

  const getInitials = (name: string) => {
    return name
      .split(' ')
      .filter((n) => n.length > 0)
      .map((n) => n[0])
      .join('')
      .substring(0, 2)
      .toUpperCase();
  };

  return (
    <Pressable
      onPress={onPress}
      onPressIn={handlePressIn}
      onPressOut={handlePressOut}
      style={(state: any) => [
        styles.container,
        state.focused && styles.focused,
      ]}
      accessibilityRole="button"
      accessibilityLabel="Open profile menu"
      aria-label="Open profile menu"
    >
      <Animated.View style={[styles.avatarWrapper, { transform: [{ scale }] }]}>
        {user?.avatarUrl ? (
          <Image
            source={{ uri: user.avatarUrl }}
            style={styles.avatar}
            resizeMode="cover"
          />
        ) : (
          <View style={styles.fallback}>
            {user?.name ? (
              <Text style={styles.initials}>{getInitials(user.name)}</Text>
            ) : (
              <UserRound size={20} color={theme.colors.textPrimary} strokeWidth={2} />
            )}
          </View>
        )}
      </Animated.View>
    </Pressable>
  );
}

const createStyles = (theme: any) => StyleSheet.create({
  container: {
    width: 44,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  focused: {
    outlineColor: theme.components.profileAvatarOutline,
    outlineStyle: 'solid',
    outlineWidth: 2,
    outlineOffset: 2,
    borderRadius: theme.radius.md,
  } as any,
  avatarWrapper: {
    width: 36,
    height: 36,
  },
  avatar: {
    width: '100%',
    height: '100%',
    borderRadius: 18,
    borderWidth: 2,
    borderColor: theme.components.profileAvatarOutline,
  },
  fallback: {
    width: '100%',
    height: '100%',
    borderRadius: 18,
    borderWidth: 2,
    borderColor: theme.components.profileAvatarOutline,
    backgroundColor: theme.colors.backgroundSubtle,
    alignItems: 'center',
    justifyContent: 'center',
  },
  initials: {
    fontSize: theme.typography.sizeSm,
    fontWeight: theme.typography.weightSemiBold,
    color: theme.colors.textPrimary,
  },
});
