import React, { useEffect } from 'react';
import { View, Text, StyleSheet, Pressable, Animated, Dimensions, Easing } from 'react-native';
import { useRouter, usePathname } from 'expo-router';
import { useAuth } from '../../app/_layout';
import { useTheme, useStyles } from '../../src/theme';
import { drawerNavigationItems } from './menu.config';
import { MesiriProfileAvatar } from './MesiriProfileAvatar';
import { LogOut } from 'lucide-react-native';

type MenuDrawerProps = {
  isOpen: boolean;
  onClose: () => void;
};

const { width } = Dimensions.get('window');
const DRAWER_WIDTH = Math.min(width * 0.85, 340);

export function MenuDrawer({ isOpen, onClose }: MenuDrawerProps) {
  const { user, signOut } = useAuth();
  const { theme } = useTheme();
  const styles = useStyles(createStyles);
  const router = useRouter();
  const pathname = usePathname();

  const slideAnim = React.useRef(new Animated.Value(-DRAWER_WIDTH)).current;
  const fadeAnim = React.useRef(new Animated.Value(0)).current;

  const [isMounted, setIsMounted] = React.useState(isOpen);

  useEffect(() => {
    if (isOpen) {
      setIsMounted(true);
      Animated.parallel([
        Animated.timing(slideAnim, {
          toValue: 0,
          duration: 250,
          easing: Easing.out(Easing.ease),
          useNativeDriver: true,
        }),
        Animated.timing(fadeAnim, {
          toValue: 1,
          duration: 250,
          useNativeDriver: true,
        })
      ]).start();
    } else {
      Animated.parallel([
        Animated.timing(slideAnim, {
          toValue: -DRAWER_WIDTH,
          duration: 200,
          easing: Easing.in(Easing.ease),
          useNativeDriver: true,
        }),
        Animated.timing(fadeAnim, {
          toValue: 0,
          duration: 200,
          useNativeDriver: true,
        })
      ]).start(() => {
        setIsMounted(false);
      });
    }
  }, [isOpen, slideAnim, fadeAnim]);

  if (!isMounted) return null;

  const handleNavigate = (route: string) => {
    onClose();
    // setTimeout to allow drawer to close before navigating to avoid heavy JS frames
    setTimeout(() => {
      router.push(route as any);
    }, 50);
  };

  const handleSignOut = () => {
    onClose();
    signOut();
  };

  const visibleItems = drawerNavigationItems.filter(item => {
    if (!item.requiredCapability) return true;
    return user?.capabilities?.includes(item.requiredCapability);
  });

  const managementItems = visibleItems.filter(i => i.section === 'management');
  const settingsItems = visibleItems.filter(i => i.section === 'settings');

  return (
    <View style={StyleSheet.absoluteFill} pointerEvents={isOpen ? 'auto' : 'none'}>
      {/* Overlay */}
      <Animated.View style={[styles.overlay, { opacity: fadeAnim }]}>
        <Pressable style={StyleSheet.absoluteFill} onPress={onClose} accessibilityLabel="Close menu" />
      </Animated.View>

      {/* Drawer */}
      <Animated.View style={[styles.drawer, { transform: [{ translateX: slideAnim }] }]}>
        
        {/* User Context Header */}
        <View style={styles.header}>
          <MesiriProfileAvatar onPress={() => {}} />
          <View style={styles.userInfo}>
            <Text style={styles.userName} numberOfLines={1}>{user?.name || 'User'}</Text>
            <Text style={styles.userRole} numberOfLines={1}>{user?.role || 'Guest'}</Text>
            <Text style={styles.userCompany} numberOfLines={1}>{user?.company || 'Mesiri'}</Text>
          </View>
        </View>

        <View style={styles.divider} />

        {/* Primary Management Navigation */}
        <View style={styles.section}>
          {managementItems.map(item => {
            const isActive = pathname.startsWith(item.route);
            return (
              <Pressable 
                key={item.id}
                style={({ pressed }) => [
                  styles.navItem, 
                  isActive && styles.navItemActive,
                  pressed && !isActive && styles.navItemPressed
                ]}
                onPress={() => handleNavigate(item.route)}
                accessibilityRole="button"
                accessibilityState={{ selected: isActive }}
              >
                <item.icon 
                  size={20} 
                  color={isActive ? theme.colors.actionPrimaryForeground : theme.colors.textMuted} 
                  strokeWidth={isActive ? 2.5 : 2}
                  style={styles.navIcon}
                />
                <Text style={[styles.navLabel, isActive && styles.navLabelActive]}>{item.label}</Text>
              </Pressable>
            );
          })}
        </View>

        <View style={styles.divider} />

        {/* Settings & Account Actions */}
        <View style={styles.section}>
          {settingsItems.map(item => {
            const isActive = pathname.startsWith(item.route);
            return (
              <Pressable 
                key={item.id}
                style={({ pressed }) => [
                  styles.navItem, 
                  isActive && styles.navItemActive,
                  pressed && !isActive && styles.navItemPressed
                ]}
                onPress={() => handleNavigate(item.route)}
                accessibilityRole="button"
                accessibilityState={{ selected: isActive }}
              >
                <item.icon 
                  size={20} 
                  color={isActive ? theme.colors.actionPrimaryForeground : theme.colors.textMuted} 
                  strokeWidth={isActive ? 2.5 : 2}
                  style={styles.navIcon}
                />
                <Text style={[styles.navLabel, isActive && styles.navLabelActive]}>{item.label}</Text>
              </Pressable>
            );
          })}
        </View>

        {/* Log Out */}
        <View style={styles.logoutContainer}>
          <Pressable 
            style={({ pressed }) => [styles.navItem, pressed && styles.navItemPressed]}
            onPress={handleSignOut}
          >
            <LogOut size={20} color={theme.colors.textMuted} strokeWidth={2} style={styles.navIcon} />
            <Text style={styles.navLabel}>Log Out</Text>
          </Pressable>
        </View>

      </Animated.View>
    </View>
  );
}

const createStyles = (theme: any) => StyleSheet.create({
  overlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0,0,0,0.5)',
    zIndex: 100,
  },
  drawer: {
    position: 'absolute',
    top: 0,
    bottom: 0,
    left: 0,
    width: DRAWER_WIDTH,
    backgroundColor: theme.colors.backgroundSurface,
    zIndex: 101,
    paddingTop: 60, // accommodate safe area roughly if no safe-area context
  },
  header: {
    paddingHorizontal: 20,
    paddingBottom: 24,
    flexDirection: 'row',
    alignItems: 'center',
  },
  userInfo: {
    marginLeft: 16,
    flex: 1,
  },
  userName: {
    fontSize: 16,
    fontWeight: theme.typography.weightBold,
    color: theme.colors.textPrimary,
  },
  userRole: {
    fontSize: 13,
    fontWeight: theme.typography.weightSemiBold,
    color: theme.colors.textMuted,
    marginTop: 2,
  },
  userCompany: {
    fontSize: 12,
    color: theme.colors.textSubtle,
    marginTop: 2,
  },
  divider: {
    height: 1,
    backgroundColor: theme.colors.borderSubtle,
    marginHorizontal: 20,
  },
  section: {
    paddingVertical: 12,
    paddingHorizontal: 12,
  },
  navItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 12,
    borderRadius: theme.radius.md,
    marginBottom: 4,
  },
  navItemPressed: {
    backgroundColor: 'rgba(15,15,15,0.04)',
  },
  navItemActive: {
    backgroundColor: theme.colors.actionPrimary,
  },
  navIcon: {
    marginRight: 16,
  },
  navLabel: {
    fontSize: 15,
    fontWeight: theme.typography.weightSemiBold,
    color: theme.colors.textPrimary,
  },
  navLabelActive: {
    color: theme.colors.actionPrimaryForeground,
  },
  logoutContainer: {
    marginTop: 'auto',
    paddingHorizontal: 12,
    paddingBottom: 40, // safe area bottom
  }
});
