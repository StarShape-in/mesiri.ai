import React from 'react';
import { View, Text, StyleSheet, Pressable } from 'react-native';
import { ChevronRight } from 'lucide-react-native';

export type ReportingStatusType = 'missing' | 'incomplete' | 'complete';

type ReportingStatusRowProps = {
  title: string;
  subtitle: string;
  status: ReportingStatusType;
  contextMessage?: string;
  timeLabel?: string;
  onPress: () => void;
};

export function ReportingStatusRow({
  title,
  subtitle,
  status,
  contextMessage,
  timeLabel,
  onPress
}: ReportingStatusRowProps) {
  
  const getStatusColor = () => {
    switch (status) {
      case 'missing': return '#DC2626'; // Red
      case 'incomplete': return '#D97706'; // Amber
      case 'complete': return '#65A30D'; // Lime/Green
      default: return '#737373';
    }
  };

  const getStatusText = () => {
    switch (status) {
      case 'missing': return 'Missing Today';
      case 'incomplete': return 'Incomplete';
      case 'complete': return 'Complete';
      default: return '';
    }
  };

  return (
    <Pressable 
      style={({ pressed }) => [styles.container, pressed && styles.pressed]}
      onPress={onPress}
      accessibilityRole="button"
    >
      <View style={[styles.indicator, { backgroundColor: getStatusColor() }]} />
      
      <View style={styles.content}>
        <Text style={styles.title} numberOfLines={1}>{title}</Text>
        <Text style={styles.subtitle} numberOfLines={1}>{subtitle}</Text>
        
        <View style={styles.statusRow}>
          <Text style={[styles.statusText, { color: getStatusColor() }]}>
            {getStatusText()}
          </Text>
          {contextMessage && (
            <Text style={styles.contextMessage} numberOfLines={1}>
              {' • '}{contextMessage}
            </Text>
          )}
        </View>
      </View>

      <View style={styles.rightContent}>
        {timeLabel && <Text style={styles.time}>{timeLabel}</Text>}
        <ChevronRight size={16} color="#A3A3A3" strokeWidth={2} />
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
  indicator: {
    width: 4,
    height: 16,
    borderRadius: 2,
    marginTop: 2,
    marginRight: 12,
  },
  content: {
    flex: 1,
    marginRight: 12,
  },
  title: {
    fontSize: 14,
    fontWeight: '600',
    color: '#111111',
    marginBottom: 2,
  },
  subtitle: {
    fontSize: 12,
    color: '#737373',
    marginBottom: 6,
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  statusText: {
    fontSize: 12,
    fontWeight: '600',
  },
  contextMessage: {
    fontSize: 12,
    color: '#737373',
    flexShrink: 1,
  },
  rightContent: {
    alignItems: 'flex-end',
    justifyContent: 'center',
    paddingTop: 4,
  },
  time: {
    fontSize: 11,
    color: '#A3A3A3',
    marginBottom: 8,
  },
});
