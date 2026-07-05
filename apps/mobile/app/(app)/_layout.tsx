import { Tabs, Link } from 'expo-router';
import { View, StyleSheet, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

export default function AppLayout() {
  return (
    <Tabs
      screenOptions={{
        headerStyle: {
          backgroundColor: '#FFFFFF', // surface-primary
          borderBottomWidth: 1,
          borderBottomColor: '#E5E7EB', // border-default
          elevation: 0,
          shadowOpacity: 0,
        },
        headerTitleStyle: {
          color: '#0E1116', // neutral-900
          fontWeight: '600',
        },
        headerTintColor: '#0E1116',
        tabBarStyle: {
          backgroundColor: '#FFFFFF', // surface-primary
          borderTopWidth: 1,
          borderTopColor: '#E5E7EB', // border-default
          paddingBottom: 8,
          paddingTop: 8,
          height: 60,
          elevation: 0,
          shadowOpacity: 0,
        },
        tabBarActiveTintColor: '#7ED957', // primary
        tabBarInactiveTintColor: '#9CA3AF', // neutral-400
        headerRight: () => (
          <Link href="/profile" asChild>
            <TouchableOpacity style={{ marginRight: 16 }}>
              <View style={styles.profileAvatar}>
                <Ionicons name="person" size={16} color="#FFFFFF" />
              </View>
            </TouchableOpacity>
          </Link>
        ),
      }}>
      <Tabs.Screen
        name="index"
        options={{
          title: 'Home',
          tabBarIcon: ({ color }) => <Ionicons name="home-outline" size={24} color={color} />,
        }}
      />
      <Tabs.Screen
        name="sites"
        options={{
          title: 'Sites',
          tabBarIcon: ({ color }) => <Ionicons name="business-outline" size={24} color={color} />,
        }}
      />
      <Tabs.Screen
        name="users"
        options={{
          title: 'Team',
          tabBarIcon: ({ color }) => <Ionicons name="people-outline" size={24} color={color} />,
        }}
      />
      <Tabs.Screen
        name="reports"
        options={{
          title: 'Reports',
          tabBarIcon: ({ color }) => <Ionicons name="document-text-outline" size={24} color={color} />,
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: 'Profile',
          href: null, // Hides this from the bottom tab bar
        }}
      />
    </Tabs>
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
