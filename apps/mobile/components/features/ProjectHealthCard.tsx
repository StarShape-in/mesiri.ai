import React from 'react';
import { View, Text, StyleSheet, Pressable } from 'react-native';
import { StatusBadge, StatusType } from '../ui/StatusBadge';
import { ChevronRight } from 'lucide-react-native';

type ProjectHealthCardProps = {
  name: string;
  location?: string;
  status: StatusType;
  statusLabel: string;
  progress: number;
  reportingRatio?: string;
  openIssues: number;
  onPress: () => void;
};

export function ProjectHealthCard({
  name,
  location,
  status,
  statusLabel,
  progress,
  reportingRatio,
  openIssues,
  onPress
}: ProjectHealthCardProps) {
  // Use lime for healthy progress, semantic color otherwise if needed, but spec says 
  // "Use Mesiri lime for normal/healthy progress."
  const isCritical = status === 'critical';

  return (
    <Pressable 
      style={({ pressed }) => [styles.card, pressed && styles.pressed]} 
      onPress={onPress}
      accessibilityRole="button"
    >
      <View style={styles.header}>
        <View style={styles.headerTextContainer}>
          <Text style={styles.name} numberOfLines={1}>{name}</Text>
          {location && <Text style={styles.location} numberOfLines={1}>{location}</Text>}
        </View>
        <ChevronRight size={18} color="#A3A3A3" strokeWidth={2} style={styles.icon} />
      </View>

      <View style={styles.statusSection}>
        <Text style={styles.label}>HEALTH STATUS</Text>
        <StatusBadge status={status} label={statusLabel} />
      </View>

      <View style={styles.metricRow}>
        <Text style={styles.metricLabel}>Progress</Text>
        <View style={styles.progressContainer}>
          <Text style={styles.metricValue}>{progress}%</Text>
          <View style={styles.progressTrack}>
            <View style={[styles.progressFill, { width: `${progress}%` }]} />
          </View>
        </View>
      </View>

      {reportingRatio && (
        <View style={styles.metricRow}>
          <Text style={styles.metricLabel}>Reporting Today</Text>
          <Text style={styles.metricValue}>{reportingRatio}</Text>
        </View>
      )}

      <View style={styles.metricRow}>
        <Text style={[styles.metricLabel, isCritical && styles.criticalLabel]}>Open Issues</Text>
        <Text style={[styles.metricValue, isCritical && styles.criticalValue]}>{openIssues}</Text>
      </View>

    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: 'rgba(15,15,15,0.08)',
    borderRadius: 14,
    padding: 16,
    marginBottom: 12,
  },
  pressed: {
    backgroundColor: '#FAFAFA',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 16,
  },
  headerTextContainer: {
    flex: 1,
    marginRight: 12,
  },
  name: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111111',
    marginBottom: 2,
  },
  location: {
    fontSize: 13,
    color: '#737373',
  },
  icon: {
    marginTop: 2,
  },
  statusSection: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  label: {
    fontSize: 11,
    fontWeight: '700',
    color: '#737373',
    letterSpacing: 0.5,
  },
  metricRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  metricLabel: {
    fontSize: 13,
    color: '#525252',
    fontWeight: '500',
  },
  criticalLabel: {
    color: '#DC2626',
  },
  metricValue: {
    fontSize: 13,
    fontWeight: '600',
    color: '#111111',
  },
  criticalValue: {
    color: '#DC2626',
  },
  progressContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    width: '45%',
    justifyContent: 'flex-end',
  },
  progressTrack: {
    width: 60,
    height: 5,
    backgroundColor: '#F3F3F3',
    borderRadius: 3,
    marginLeft: 8,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    backgroundColor: '#B7F52A',
    borderRadius: 3,
  },
});
