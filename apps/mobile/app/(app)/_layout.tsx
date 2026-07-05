import { Tabs } from 'expo-router';
import { View, StyleSheet } from 'react-native';

export default function AppLayout() {
  return (
    <Tabs
      screenOptions={{
        headerStyle: {
          backgroundColor: '#0F172A',
          borderBottomWidth: 1,
          borderBottomColor: '#1E293B',
        },
        headerTintColor: '#FFFFFF',
        tabBarStyle: {
          backgroundColor: '#0F172A',
          borderTopWidth: 1,
          borderTopColor: '#1E293B',
          paddingBottom: 8,
          paddingTop: 8,
          height: 60,
        },
        tabBarActiveTintColor: '#3B82F6',
        tabBarInactiveTintColor: '#64748B',
      }}>
      <Tabs.Screen
        name="index"
        options={{
          title: 'Home',
          tabBarIcon: ({ color }) => (
            <View style={[styles.iconPlaceholder, { backgroundColor: color }]} />
          ),
        }}
      />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  iconPlaceholder: {
    width: 24,
    height: 24,
    borderRadius: 6,
    opacity: 0.8,
  },
});
