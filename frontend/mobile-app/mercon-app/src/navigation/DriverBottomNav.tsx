/**
 * Driver App Bottom Navigation
 * Dark floating pill with 3 items: Home, Trips, Profile.
 * The active item is marked by an orange "capsule" (icon + label) that gently
 * settles in when the page changes; inactive items show a dim icon only.
 * Route-based (expo-router).
 */
import React, { useEffect, useRef } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Animated } from 'react-native';
import { usePathname, useRouter } from 'expo-router';
import { House, Truck, User, type LucideIcon } from 'lucide-react-native';
import { Colors, Spacing, Radius, Shadows } from '../theme/tokens';

export type DriverTab = 'Home' | 'Trips' | 'Profile';

interface DriverBottomNavProps {
  // Kept optional for backwards compatibility with screens that still pass them;
  // navigation is now driven by the router, so these are ignored.
  activeTab?: DriverTab | string;
  onTabPress?: (tab: DriverTab) => void;
}

const TABS: { label: DriverTab; Icon: LucideIcon; route: string }[] = [
  { label: 'Home',    Icon: House, route: '/' },
  { label: 'Trips',   Icon: Truck, route: '/trips' },
  { label: 'Profile', Icon: User,  route: '/profile' },
];

const INACTIVE = 'rgba(255,255,255,0.55)';

export function DriverBottomNav(_props: DriverBottomNavProps = {}) {
  const router = useRouter();
  const pathname = usePathname();

  // Capsule settles in when the active page changes. Start fully visible (1) so the
  // first paint doesn't flash or hide the capsule before/during navigation.
  const anim = useRef(new Animated.Value(1)).current;
  useEffect(() => {
    anim.setValue(0.95);
    Animated.spring(anim, { toValue: 1, useNativeDriver: true, friction: 9, tension: 120 }).start();
  }, [pathname, anim]);

  const capsuleStyle = {
    opacity: anim,
    transform: [{ scale: anim.interpolate({ inputRange: [0.95, 1], outputRange: [0.96, 1] }) }],
  };

  return (
    <View style={styles.wrapper}>
      <View style={[styles.pill, Shadows.nav]}>
        {TABS.map(({ label, Icon, route }) => {
          const active = route === '/' ? pathname === '/' : pathname.startsWith(route);
          return (
            <TouchableOpacity
              key={label}
              onPress={() => { if (!active) router.navigate(route as any); }}
              activeOpacity={0.7}
              style={styles.tab}
            >
              {active ? (
                <Animated.View style={[styles.capsule, capsuleStyle]}>
                  <Icon size={22} color={Colors.white} strokeWidth={2.4} />
                  <Text style={styles.capsuleLabel}>{label}</Text>
                </Animated.View>
              ) : (
                <Icon size={24} color={INACTIVE} strokeWidth={2} />
              )}
            </TouchableOpacity>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.sm,
    paddingBottom: 0,
    marginBottom: -Spacing.sm, // sit low, close to the screen edge
  },
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-around',
    backgroundColor: Colors.navBg,
    borderRadius: Radius.full,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm + 2,
  },
  tab: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    height: 50,
  },
  capsule: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
    backgroundColor: Colors.primary,
    borderRadius: Radius.full,
    paddingHorizontal: Spacing.base,
    paddingVertical: Spacing.sm + 2,
  },
  capsuleLabel: {
    fontSize: 14,
    fontWeight: '700',
    color: Colors.white,
  },
});
