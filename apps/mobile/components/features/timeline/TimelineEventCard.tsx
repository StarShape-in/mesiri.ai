import React from 'react';
import { View, Text, StyleSheet, Pressable } from 'react-native';
import { useTheme, useStyles } from '../../../src/theme';
import { TimelineEvent } from '../../../src/services/timelineService';
import { getCategoryConfig } from '../../../src/config/timelineCategories';

type TimelineEventCardProps = {
  event: TimelineEvent;
  scopeChip?: { label: string; color: string } | null;
  onPress?: (event: TimelineEvent) => void;
  isLast?: boolean;
};

function formatTime(occurredAt: string): string {
  const d = new Date(occurredAt);
  if (isNaN(d.getTime())) return '';
  return d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
}

export function TimelineEventCard({ event, scopeChip, onPress, isLast }: TimelineEventCardProps) {
  const { theme } = useTheme();
  const styles = useStyles(createStyles);
  const config = getCategoryConfig(event.eventType);
  const dotColor = (theme.colors as any)[config.dotColorToken] ?? theme.colors.statusNeutral;
  const isViaWhatsApp = typeof event.payload?.source === 'string' && event.payload.source !== 'mobile';

  return (
    <View style={styles.row}>
      <View style={styles.railColumn}>
        <View
          style={[
            styles.dot,
            config.dotStyle === 'filled'
              ? { backgroundColor: dotColor }
              : { backgroundColor: 'transparent', borderWidth: 2, borderColor: dotColor },
          ]}
        />
        {!isLast && <View style={styles.railLine} />}
      </View>
      <Pressable
        style={styles.card}
        onPress={onPress ? () => onPress(event) : undefined}
        disabled={!onPress}
      >
        <View style={styles.topRow}>
          <Text style={styles.title} numberOfLines={2}>
            {event.summary}
          </Text>
          <Text style={styles.time}>{formatTime(event.occurredAt)}</Text>
        </View>
        {scopeChip && (
          <View style={styles.chipRow}>
            <View style={[styles.chip, { backgroundColor: `${scopeChip.color}20` }]}>
              <View style={[styles.chipDot, { backgroundColor: scopeChip.color }]} />
              <Text style={[styles.chipText, { color: scopeChip.color }]} numberOfLines={1}>
                {scopeChip.label}
              </Text>
            </View>
          </View>
        )}
        {isViaWhatsApp && (
          <View style={styles.footerRow}>
            <Text style={styles.sourceTag}>via WhatsApp</Text>
          </View>
        )}
      </Pressable>
    </View>
  );
}

const createStyles = (theme: any) => StyleSheet.create({
  row: {
    flexDirection: 'row',
  },
  railColumn: {
    width: 20,
    alignItems: 'center',
  },
  dot: {
    width: 11,
    height: 11,
    borderRadius: 6,
    marginTop: 6,
  },
  railLine: {
    flex: 1,
    width: 2,
    backgroundColor: theme.colors.borderDefault,
    marginTop: 2,
  },
  card: {
    flex: 1,
    marginLeft: theme.spacing.space2,
    marginBottom: theme.spacing.space3,
    backgroundColor: theme.colors.backgroundSurface,
    borderWidth: 1,
    borderColor: theme.colors.borderSubtle,
    borderRadius: theme.radius.lg,
    padding: theme.spacing.space3,
  },
  topRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  title: {
    flex: 1,
    marginRight: 8,
    fontSize: theme.typography.sizeSm,
    fontWeight: theme.typography.weightSemiBold,
    color: theme.colors.textPrimary,
  },
  time: {
    fontSize: 11,
    color: theme.colors.textMuted,
  },
  chipRow: {
    flexDirection: 'row',
    marginTop: 6,
  },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: theme.radius.full,
    maxWidth: '80%',
  },
  chipDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    marginRight: 5,
  },
  chipText: {
    fontSize: 11,
    fontWeight: theme.typography.weightMedium,
  },
  footerRow: {
    flexDirection: 'row',
    marginTop: 6,
    paddingTop: 6,
    borderTopWidth: 1,
    borderTopColor: 'rgba(15,15,15,0.02)',
  },
  sourceTag: {
    fontSize: 10,
    fontWeight: theme.typography.weightSemiBold,
    textTransform: 'uppercase',
    color: theme.colors.textMuted,
    backgroundColor: theme.colors.backgroundSubtle,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
});
