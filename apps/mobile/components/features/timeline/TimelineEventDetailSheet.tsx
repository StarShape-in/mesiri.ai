import React from 'react';
import { View, Text, StyleSheet, Modal, Pressable } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useTheme, useStyles } from '../../../src/theme';
import { TimelineEvent } from '../../../src/services/timelineService';
import { getCategoryConfig } from '../../../src/config/timelineCategories';

type TimelineEventDetailSheetProps = {
  event: TimelineEvent | null;
  onClose: () => void;
};

function formatDateTime(occurredAt: string): string {
  const d = new Date(occurredAt);
  if (isNaN(d.getTime())) return occurredAt;
  return d.toLocaleString(undefined, {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

export function TimelineEventDetailSheet({ event, onClose }: TimelineEventDetailSheetProps) {
  const { theme } = useTheme();
  const styles = useStyles(createStyles);

  if (!event) return null;

  const config = getCategoryConfig(event.eventType);
  const isViaWhatsApp = typeof event.payload?.source === 'string' && event.payload.source !== 'mobile';
  const payloadEntries = Object.entries(event.payload || {}).filter(
    ([key]) => !['source', 'occurred_date_source'].includes(key)
  );

  return (
    <Modal visible transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.overlay} onPress={onClose}>
        <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
          <View style={styles.header}>
            <Text style={styles.title}>{config.label}</Text>
            <Pressable onPress={onClose} hitSlop={12}>
              <Ionicons name="close" size={22} color={theme.colors.textSecondary} />
            </Pressable>
          </View>

          <Text style={styles.summary}>{event.summary}</Text>
          <Text style={styles.dateText}>{formatDateTime(event.occurredAt)}</Text>

          {payloadEntries.length > 0 && (
            <View style={styles.detailsBlock}>
              {payloadEntries.map(([key, value]) => (
                <View key={key} style={styles.detailRow}>
                  <Text style={styles.detailKey}>{key.replace(/_/g, ' ')}</Text>
                  <Text style={styles.detailValue} numberOfLines={2}>
                    {String(value)}
                  </Text>
                </View>
              ))}
            </View>
          )}

          {isViaWhatsApp && (
            <View style={styles.footerRow}>
              <Text style={styles.sourceTag}>via WhatsApp</Text>
            </View>
          )}
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const createStyles = (theme: any) => StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: theme.colors.backgroundSurface,
    borderTopLeftRadius: theme.radius.xl,
    borderTopRightRadius: theme.radius.xl,
    padding: theme.spacing.space6,
    paddingBottom: 40,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: theme.spacing.space3,
  },
  title: {
    fontSize: theme.typography.sizeLg,
    fontWeight: theme.typography.weightBold,
    color: theme.colors.textPrimary,
  },
  summary: {
    fontSize: theme.typography.sizeMd,
    fontWeight: theme.typography.weightSemiBold,
    color: theme.colors.textPrimary,
    marginBottom: 4,
  },
  dateText: {
    fontSize: theme.typography.sizeSm,
    color: theme.colors.textMuted,
    marginBottom: theme.spacing.space4,
  },
  detailsBlock: {
    borderTopWidth: 1,
    borderTopColor: theme.colors.borderDefault,
    paddingTop: theme.spacing.space3,
    gap: 8,
  },
  detailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 12,
  },
  detailKey: {
    fontSize: 13,
    color: theme.colors.textMuted,
    textTransform: 'capitalize',
  },
  detailValue: {
    flex: 1,
    fontSize: 13,
    color: theme.colors.textPrimary,
    textAlign: 'right',
  },
  footerRow: {
    marginTop: theme.spacing.space4,
    alignItems: 'flex-start',
  },
  sourceTag: {
    fontSize: 10,
    fontWeight: theme.typography.weightSemiBold,
    textTransform: 'uppercase',
    color: theme.colors.textMuted,
    backgroundColor: theme.colors.backgroundSubtle,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
  },
});
