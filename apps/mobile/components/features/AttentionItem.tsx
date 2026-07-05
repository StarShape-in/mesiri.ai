import React from 'react';
import { View, Text, StyleSheet, Pressable } from 'react-native';
import { ChevronRight } from 'lucide-react-native';

export type AttentionSeverity = 'critical' | 'warning';

type AttentionItemProps = {
  title: string;
  context: string;
  detail?: string;
  severity: AttentionSeverity;
  onPress: () => void;
};

export function AttentionItem({ title, context, detail, severity, onPress }: AttentionItemProps) {
  const indicatorColor = severity === 'critical' ? '#DC2626' : '#D97706';

  return (
    <Pressable 
      style={({ pressed }) => [styles.card, pressed && styles.pressed]} 
      onPress={onPress}
      accessibilityRole="button"
    >
      <View style={[styles.indicator, { backgroundColor: indicatorColor }]} />
      
      <View style={styles.content}>
        <Text style={styles.title} numberOfLines={1}>{title}</Text>
        <Text style={styles.context} numberOfLines={1}>{context}</Text>
        {detail && <Text style={styles.detail} numberOfLines={1}>{detail}</Text>}
      </View>

      <ChevronRight size={16} color="#A3A3A3" strokeWidth={2} style={styles.icon} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: 'rgba(15, 15, 15, 0.08)',
    borderRadius: 14,
    padding: 14,
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  pressed: {
    backgroundColor: '#FAFAFA',
  },
  indicator: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginTop: 5,
    marginRight: 12,
  },
  content: {
    flex: 1,
    justifyContent: 'center',
  },
  title: {
    fontSize: 14,
    fontWeight: '600',
    color: '#111111',
    marginBottom: 2,
  },
  context: {
    fontSize: 12,
    fontWeight: '500',
    color: '#737373',
    marginBottom: 4,
  },
  detail: {
    fontSize: 12,
    color: '#A3A3A3',
  },
  icon: {
    marginLeft: 8,
    alignSelf: 'center',
  },
});
