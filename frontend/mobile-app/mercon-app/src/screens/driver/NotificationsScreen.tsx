import React, { useState } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, SafeAreaView, StatusBar,
  FlatList, ActivityIndicator, RefreshControl,
} from 'react-native';
import { TriangleAlert, BellOff } from 'lucide-react-native';
import { Colors, Spacing, Radius, Typography, Shadows } from '../../theme/tokens';
import { DriverBottomNav } from '../../navigation/DriverBottomNav';
import { useNotifications } from '../../lib/use-notifications';
import { notificationIcon, timeAgo, type MobileNotification } from '../../lib/notifications';

const NotificationCard = ({ item, onPress }: { item: MobileNotification; onPress: () => void }) => {
  const unread = !item.is_read;
  const Icon = notificationIcon(item.type);
  return (
    <TouchableOpacity
      style={[styles.card, unread ? styles.cardUnread : null]}
      activeOpacity={0.8}
      onPress={onPress}
    >
      <View style={[styles.iconBox, unread ? styles.iconBoxUnread : null]}>
        <Icon size={20} color={unread ? Colors.primary : Colors.gray500} strokeWidth={2} />
      </View>
      <View style={styles.content}>
        <View style={styles.contentHeader}>
          <Text style={styles.title}>{item.title}</Text>
          <Text style={styles.time}>{timeAgo(item.createdAt)}</Text>
        </View>
        <Text style={styles.body} numberOfLines={2}>{item.message}</Text>
      </View>
      {unread && <View style={styles.unreadDot} />}
    </TouchableOpacity>
  );
};

const NotificationsScreen = ({ navigation }: any) => {
  const [activeTab, setActiveTab] = useState('Home');
  const { items, loading, error, refetch, markRead, markAll } = useNotifications();

  const unreadCount = items.filter((n) => !n.is_read).length;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.gray100 }}>
      <StatusBar barStyle="dark-content" backgroundColor={Colors.white} />
      <View style={styles.header}>
        <View>
          <Text style={styles.headerTitle}>Notifications</Text>
          {unreadCount > 0 && (
            <Text style={styles.unreadCount}>{unreadCount} unread</Text>
          )}
        </View>
        {unreadCount > 0 && (
          <TouchableOpacity style={styles.markAllBtn} activeOpacity={0.8} onPress={markAll}>
            <Text style={styles.markAllText}>Mark all read</Text>
          </TouchableOpacity>
        )}
      </View>

      <FlatList
        data={items}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl refreshing={loading && items.length > 0} onRefresh={refetch} />
        }
        renderItem={({ item }) => (
          <NotificationCard item={item} onPress={() => markRead(item.id)} />
        )}
        ListEmptyComponent={
          loading ? (
            <View style={styles.emptyState}>
              <ActivityIndicator color={Colors.primary} />
            </View>
          ) : error ? (
            <View style={styles.emptyState}>
              <TriangleAlert size={44} color={Colors.gray400} strokeWidth={1.6} />
              <Text style={styles.emptyTitle}>Couldn't load notifications</Text>
              <Text style={styles.emptyText}>{error}</Text>
            </View>
          ) : (
            <View style={styles.emptyState}>
              <BellOff size={44} color={Colors.gray400} strokeWidth={1.6} />
              <Text style={styles.emptyTitle}>All Caught Up</Text>
              <Text style={styles.emptyText}>No new notifications.</Text>
            </View>
          )
        }
      />
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  header: {
    backgroundColor: Colors.white,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: Colors.gray100,
  },
  headerTitle: {
    fontSize: Typography.xl,
    fontWeight: '800',
    color: Colors.gray900,
  },
  unreadCount: {
    fontSize: Typography.xs,
    color: Colors.primary,
    fontWeight: '600',
    marginTop: 2,
  },
  markAllBtn: {
    paddingVertical: Spacing.xs,
    paddingHorizontal: Spacing.sm,
  },
  markAllText: {
    fontSize: Typography.sm,
    color: Colors.primary,
    fontWeight: '600',
  },
  list: {
    padding: Spacing.lg,
    gap: Spacing.sm,
    paddingBottom: 80,
  },
  card: {
    backgroundColor: Colors.white,
    borderRadius: Radius.xl,
    padding: Spacing.md,
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: Spacing.md,
    ...Shadows.sm,
  },
  cardUnread: {
    borderLeftWidth: 3,
    borderLeftColor: Colors.primary,
  },
  iconBox: {
    width: 44,
    height: 44,
    borderRadius: Radius.lg,
    backgroundColor: Colors.gray100,
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  iconBoxUnread: {
    backgroundColor: '#FFF7ED',
  },
  content: {
    flex: 1,
  },
  contentHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 3,
    gap: Spacing.sm,
  },
  title: {
    fontSize: Typography.sm,
    fontWeight: '700',
    color: Colors.gray900,
    flex: 1,
  },
  time: {
    fontSize: Typography.xs,
    color: Colors.gray400,
    flexShrink: 0,
  },
  body: {
    fontSize: Typography.xs,
    color: Colors.gray600,
    lineHeight: 18,
  },
  unreadDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: Colors.primary,
    marginTop: Spacing.xs,
    flexShrink: 0,
  },
  emptyState: {
    alignItems: 'center',
    paddingTop: Spacing['3xl'],
    gap: Spacing.sm,
  },
  emptyTitle: {
    fontSize: Typography.lg,
    fontWeight: '700',
    color: Colors.gray700,
  },
  emptyText: {
    fontSize: Typography.sm,
    color: Colors.gray500,
  },
});

export default NotificationsScreen;
