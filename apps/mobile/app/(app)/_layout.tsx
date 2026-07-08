import React, { useState } from 'react';
import { Tabs, Link, useRouter, usePathname } from 'expo-router';
import { View, StyleSheet, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { MesiriBottomNavigation, MesiriTopBar, MenuDrawer } from '../../components/navigation';
import { ScopeProvider } from '../../state/ScopeProvider';
import { MesiriScopeBar } from '../../components/scope';
import { ProjectItem, SiteItem } from '../../components/scope';

// Mock data for authorized projects/sites since there is no backend yet
const mockProjects: ProjectItem[] = [
  { id: '1', name: 'Skyline Commercial Towers Phase 2' },
  { id: '2', name: 'Green Valley Residences' },
];

const mockSites: Record<string, SiteItem[]> = {
  '1': [
    { id: '1a', name: 'Block A', projectId: '1' },
    { id: '1b', name: 'Block B', projectId: '1' },
  ],
  '2': [
    { id: '2a', name: 'Tower 1', projectId: '2' },
  ]
};

export default function AppLayout() {
  const router = useRouter();
  const pathname = usePathname();
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  const hideScopeBar = pathname.startsWith('/settings');
  const hideBottomNav = pathname.startsWith('/settings') || pathname.startsWith('/projects/new');

  return (
    <ScopeProvider>
      <View style={{ flex: 1 }}>
        <Tabs
          tabBar={() => hideBottomNav ? null : <MesiriBottomNavigation />}
          screenOptions={{
            header: () => (
              <View style={{ zIndex: 50 }}>
                <MesiriTopBar
                  onMenuClick={() => setIsDrawerOpen(true)}
                  onProfileClick={() => router.push('/profile')}
                  sticky={false} 
                />
                {!hideScopeBar && (
                  <MesiriScopeBar projects={mockProjects} sitesByProject={mockSites} />
                )}
              </View>
            ),
          }}>
      <Tabs.Screen name="index" options={{ title: 'Home' }} />
      <Tabs.Screen name="timeline" options={{ title: 'Timeline' }} />
      <Tabs.Screen name="analytics" options={{ title: 'Analytics' }} />
      <Tabs.Screen name="field" options={{ title: 'Field' }} />
      <Tabs.Screen name="users" options={{ title: 'Team' }} />
      <Tabs.Screen name="profile" options={{ title: 'Profile' }} />
      
      {/* Hidden fallback screens from earlier if needed */}
      <Tabs.Screen name="sites" options={{ title: 'Sites', href: null }} />
      <Tabs.Screen name="reports" options={{ title: 'Reports', href: null }} />
      <Tabs.Screen name="projects/index" options={{ title: 'Projects', href: null }} />
      <Tabs.Screen name="projects/new" options={{ title: 'New Project', href: null }} />
      <Tabs.Screen name="projects/[id]" options={{ title: 'Project Details', href: null }} />
      <Tabs.Screen name="settings/theme" options={{ title: 'Theme', href: null }} />
      <Tabs.Screen name="users/[id]" options={{ title: 'User Details', href: null }} />
    </Tabs>
    <MenuDrawer isOpen={isDrawerOpen} onClose={() => setIsDrawerOpen(false)} />
    </View>
    </ScopeProvider>
  );
}

const styles = StyleSheet.create({
  profileAvatar: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: '#1F222B', // neutral-800
    justifyContent: 'center',
    alignItems: 'center',
  },
});
