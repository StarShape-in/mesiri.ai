import React from 'react';
import { View, Text, StyleSheet, Pressable } from 'react-native';
import { LucideIcon } from 'lucide-react-native';

type ActivityItemProps = {
  title: string;
  context: string;
  timeLabel: string;
  Icon: LucideIcon;
  onPress: () => void;
};

export function ActivityItem({ title, context, timeLabel, Icon, onPress }: ActivityItemProps) {
  return (
    <Pressable 
      style={({ pressed }) => [styles.container, pressed && styles.pressed]}
      onPress={onPress}
      accessibilityRole="button"
    >
      <View style={styles.iconContainer}>
        <Icon size={18} color="#525252" strokeWidth={2} />
      </View>
      <View style={styles.content}>
        <Text style={styles.title} numberOfLines={1}>{title}</Text>
        <View style={styles.metaRow}>
          <Text style={styles.context} numberOfLines={1}>{context}</Text>
          <Text style={styles.time}>{timeLabel}</Text>
        </View>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(15,15,15,0.04)',
  },
  pressed: {
    backgroundColor: '#FAFAFA',
  },
  iconContainer: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#F3F3F3',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  content: {
    flex: 1,
    justifyContent: 'center',
    paddingTop: 2,
  },
  title: {
    fontSize: 14,
    fontWeight: '600',
    color: '#111111',
    marginBottom: 4,
  },
  metaRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  context: {
    flex: 1,
    fontSize: 12,
    color: '#737373',
    marginRight: 8,
  },
  time: {
    fontSize: 11,
    color: '#A3A3A3',
    fontWeight: '500',
  },
});
