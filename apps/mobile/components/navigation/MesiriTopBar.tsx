import React, { useRef } from 'react';
import { View, Text, StyleSheet, Pressable, Animated, Platform } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Menu } from 'lucide-react-native';
import { MesiriProfileAvatar, MesiriProfileAvatarProps } from './MesiriProfileAvatar';
import { useTheme, useStyles } from '../../src/theme';

export type MesiriTopBarProps = {
  user?: MesiriProfileAvatarProps['user'];
  onMenuClick: () => void;
  onProfileClick: () => void;
  sticky?: boolean;
};

export function MesiriTopBar({ user, onMenuClick, onProfileClick, sticky = true }: MesiriTopBarProps) {
  const insets = useSafeAreaInsets();
  const menuScale = useRef(new Animated.Value(1)).current;
  const { theme } = useTheme();
  const styles = useStyles(createStyles);

  const handleMenuPressIn = () => {
    Animated.timing(menuScale, {
      toValue: 0.94,
      duration: 100,
      useNativeDriver: true,
    }).start();
  };

  const handleMenuPressOut = () => {
    Animated.timing(menuScale, {
      toValue: 1,
      duration: 150,
      useNativeDriver: true,
    }).start();
  };

  return (
    <View 
      style={[
        styles.wrapper,
        sticky && styles.sticky,
        { paddingTop: Math.max(insets.top, 0) }
      ]}
      accessibilityRole="header"
    >
      <View style={styles.container}>
        {/* Left: Menu */}
        <Pressable
          onPress={onMenuClick}
          onPressIn={handleMenuPressIn}
          onPressOut={handleMenuPressOut}
          style={(state: any) => [
            styles.menuButton,
            state.hovered && styles.menuButtonHovered,
            state.focused && styles.focused,
          ]}
          accessibilityRole="button"
          accessibilityLabel="Open menu"
          aria-label="Open menu"
        >
          <Animated.View style={{ transform: [{ scale: menuScale }] }}>
            <Menu size={24} color={theme.colors.textPrimary} strokeWidth={2.25} />
          </Animated.View>
        </Pressable>

        {/* Center: Wordmark */}
        <View style={styles.wordmarkContainer} pointerEvents="none">
          <Text style={styles.wordmark}>mesiri</Text>
        </View>

        {/* Right: Profile Avatar */}
        <View style={styles.rightContainer}>
          <MesiriProfileAvatar user={user} onPress={onProfileClick} />
        </View>
      </View>
    </View>
  );
}

const createStyles = (theme: any) => StyleSheet.create({
  wrapper: {
    backgroundColor: theme.components.topbarBackground,
    borderBottomWidth: 1,
    borderBottomColor: theme.components.topbarBorder,
    zIndex: theme.zIndex.stickyHeader,
  },
  sticky: {
    ...Platform.select({
      web: {
        position: 'sticky',
        top: 0,
      },
      default: {
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
      }
    }) as any,
  },
  container: {
    height: 60,
    width: '100%',
    maxWidth: 520,
    marginHorizontal: 'auto',
    alignSelf: 'center',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: theme.spacing.space4, // 16
  },
  menuButton: {
    width: 44,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: theme.radius.lg,
    backgroundColor: 'transparent',
  },
  menuButtonHovered: {
    backgroundColor: theme.colors.backgroundSubtle,
  } as any,
  focused: {
    outlineColor: theme.colors.focusRing,
    outlineStyle: 'solid',
    outlineWidth: 2,
    outlineOffset: 2,
  } as any,
  wordmarkContainer: {
    position: 'absolute',
    left: 0,
    right: 0,
    alignItems: 'center',
    justifyContent: 'center',
  },
  wordmark: {
    fontSize: theme.typography.sizeXl + 1, // 21px
    fontWeight: theme.typography.weightBold,
    color: theme.colors.textPrimary,
    letterSpacing: -0.84, // -0.04em for 21px font size
    lineHeight: 21,
    fontFamily: Platform.select({ ios: theme.typography.familySans, android: 'sans-serif', web: 'inherit' }),
  },
  rightContainer: {
    width: 44,
    height: 44,
    alignItems: 'flex-end',
    justifyContent: 'center',
  },
});
