import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ActivityIndicator } from 'react-native';
import { useTheme, useStyles } from '../../../src/theme';
import { EmptyState } from '../../ui/EmptyState';
import { materialsService, MaterialUsage } from '../../../src/services/materialsService';
import { ArrowUpRight, AlertCircle } from 'lucide-react-native';

type MaterialOutflowsListProps = {
  projectId?: string;
  siteId?: string;
  searchQuery: string;
  dateFrom?: string;
  dateTo?: string;
  refreshTrigger: number;
  onRefreshComplete: () => void;
};

export function MaterialOutflowsList({
  projectId,
  siteId,
  searchQuery,
  dateFrom,
  dateTo,
  refreshTrigger,
  onRefreshComplete,
}: MaterialOutflowsListProps) {
  const { theme } = useTheme();
  const styles = useStyles(createStyles);

  const [outflows, setOutflows] = useState<MaterialUsage[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function loadOutflows() {
      setIsLoading(true);
      setError(null);
      try {
        const res = await materialsService.getOutflows({
          project_id: projectId,
          site_id: siteId,
          material_name: searchQuery || undefined,
          date_from: dateFrom || undefined,
          date_to: dateTo || undefined,
          limit: 100,
        });
        if (active) {
          setOutflows(res.items);
        }
      } catch (err: any) {
        if (active) {
          setError('Failed to load outflows');
        }
      } finally {
        if (active) {
          setIsLoading(false);
          onRefreshComplete();
        }
      }
    }

    loadOutflows();
    return () => {
      active = false;
    };
  }, [projectId, siteId, searchQuery, dateFrom, dateTo, refreshTrigger, onRefreshComplete]);

  if (isLoading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="small" color={theme.colors.textPrimary} />
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.centerContainer}>
        <AlertCircle size={24} color={theme.colors.statusDanger} style={styles.errorIcon} />
        <Text style={styles.errorText}>{error}</Text>
      </View>
    );
  }

  if (outflows.length === 0) {
    return (
      <EmptyState
        message="No outflows found matching the current filters."
        Icon={ArrowUpRight}
      />
    );
  }

  return (
    <View style={styles.container}>
      {outflows.map((usage) => (
        <View key={usage.id} style={styles.card}>
          <View style={styles.iconWrapper}>
            <ArrowUpRight size={16} color={theme.colors.statusDangerForeground} />
          </View>
          <View style={styles.details}>
            <View style={styles.row}>
              <Text style={styles.materialName} numberOfLines={1}>{usage.materialName}</Text>
              <Text style={styles.quantity}>{usage.quantity} {usage.unit}</Text>
            </View>
            <View style={styles.row}>
              <Text style={styles.workItem} numberOfLines={1}>
                {usage.workItem || 'General Usage / No Work Item'}
              </Text>
            </View>
            <View style={styles.footerRow}>
              <Text style={styles.date}>{usage.occurredDate}</Text>
              <Text style={styles.sourceTag}>{usage.source}</Text>
            </View>
          </View>
        </View>
      ))}
    </View>
  );
}

const createStyles = (theme: any) => StyleSheet.create({
  container: {
    gap: 12,
    marginTop: theme.spacing.space2,
  },
  loadingContainer: {
    padding: 40,
    alignItems: 'center',
  },
  centerContainer: {
    padding: 32,
    alignItems: 'center',
    justifyContent: 'center',
  },
  errorIcon: {
    marginBottom: 8,
  },
  errorText: {
    fontSize: theme.typography.sizeSm,
    color: theme.colors.textMuted,
  },
  card: {
    flexDirection: 'row',
    backgroundColor: theme.colors.backgroundSurface,
    borderWidth: 1,
    borderColor: theme.colors.borderSubtle,
    borderRadius: theme.radius.lg,
    padding: theme.spacing.space3,
    alignItems: 'center',
  },
  iconWrapper: {
    width: 32,
    height: 32,
    borderRadius: theme.radius.full,
    backgroundColor: theme.colors.statusDangerBackground,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: theme.spacing.space3,
  },
  details: {
    flex: 1,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 2,
  },
  materialName: {
    fontSize: theme.typography.sizeSm,
    fontWeight: theme.typography.weightSemiBold,
    color: theme.colors.textPrimary,
    flex: 1,
    marginRight: 8,
  },
  quantity: {
    fontSize: theme.typography.sizeSm,
    fontWeight: theme.typography.weightBold,
    color: theme.colors.textPrimary,
  },
  workItem: {
    fontSize: 12,
    color: theme.colors.textMuted,
  },
  footerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 6,
    paddingTop: 6,
    borderTopWidth: 1,
    borderTopColor: 'rgba(15,15,15,0.02)',
  },
  date: {
    fontSize: 11,
    color: theme.colors.textMuted,
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
