import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ActivityIndicator } from 'react-native';
import { useTheme, useStyles } from '../../../src/theme';
import { EmptyState } from '../../ui/EmptyState';
import { materialsService, MaterialReceipt } from '../../../src/services/materialsService';
import { ArrowDownLeft, AlertCircle } from 'lucide-react-native';

type MaterialInflowsListProps = {
  projectId?: string;
  siteId?: string;
  searchQuery: string;
  dateFrom?: string;
  dateTo?: string;
  refreshTrigger: number;
  onRefreshComplete: () => void;
};

export function MaterialInflowsList({
  projectId,
  siteId,
  searchQuery,
  dateFrom,
  dateTo,
  refreshTrigger,
  onRefreshComplete,
}: MaterialInflowsListProps) {
  const { theme } = useTheme();
  const styles = useStyles(createStyles);

  const [inflows, setInflows] = useState<MaterialReceipt[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function loadInflows() {
      setIsLoading(true);
      setError(null);
      try {
        const res = await materialsService.getInflows({
          project_id: projectId,
          site_id: siteId,
          material_name: searchQuery || undefined,
          date_from: dateFrom || undefined,
          date_to: dateTo || undefined,
          limit: 100,
        });
        if (active) {
          setInflows(res.items);
        }
      } catch (err: any) {
        if (active) {
          setError('Failed to load inflows');
        }
      } finally {
        if (active) {
          setIsLoading(false);
          onRefreshComplete();
        }
      }
    }

    loadInflows();
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

  if (inflows.length === 0) {
    return (
      <EmptyState
        message="No inflows found matching the current filters."
        Icon={ArrowDownLeft}
      />
    );
  }

  return (
    <View style={styles.container}>
      {inflows.map((receipt) => {
        const costText = receipt.totalCost !== null ? `₹${receipt.totalCost}` : receipt.unitCost !== null ? `₹${receipt.unitCost}/unit` : null;
        return (
          <View key={receipt.id} style={styles.card}>
            <View style={styles.iconWrapper}>
              <ArrowDownLeft size={16} color={theme.colors.statusSuccessForeground} />
            </View>
            <View style={styles.details}>
              <View style={styles.row}>
                <Text style={styles.materialName} numberOfLines={1}>{receipt.materialName}</Text>
                <Text style={styles.quantity}>{receipt.quantity} {receipt.unit}</Text>
              </View>
              <View style={styles.row}>
                <Text style={styles.supplier} numberOfLines={1}>
                  {receipt.supplier || 'Unknown Supplier'}
                </Text>
                {costText && <Text style={styles.cost}>{costText}</Text>}
              </View>
              <View style={styles.footerRow}>
                <Text style={styles.date}>{receipt.occurredDate}</Text>
                <Text style={styles.sourceTag}>{receipt.source}</Text>
              </View>
            </View>
          </View>
        );
      })}
    </View>
  );
}

const createStyles = (theme: any) => StyleSheet.create({
  container: {
    gap: 14,
    marginTop: theme.spacing.space3,
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
    borderColor: theme.colors.borderDefault,
    borderRadius: theme.radius.lg,
    padding: theme.spacing.space4,
    alignItems: 'flex-start',
    ...theme.shadow.subtle,
  },
  iconWrapper: {
    width: 40,
    height: 40,
    borderRadius: theme.radius.full,
    backgroundColor: theme.colors.statusSuccessBackground,
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
    marginBottom: 4,
  },
  materialName: {
    fontSize: theme.typography.sizeMd,
    fontWeight: theme.typography.weightSemiBold,
    color: theme.colors.textPrimary,
    flex: 1,
    marginRight: 8,
  },
  quantity: {
    fontSize: theme.typography.sizeMd,
    fontWeight: theme.typography.weightBold,
    color: theme.colors.textPrimary,
  },
  supplier: {
    fontSize: theme.typography.sizeSm,
    color: theme.colors.textSecondary,
    flex: 1,
    marginRight: 8,
  },
  cost: {
    fontSize: theme.typography.sizeSm,
    fontWeight: theme.typography.weightMedium,
    color: theme.colors.textSecondary,
  },
  footerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 10,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: theme.colors.borderSubtle,
  },
  date: {
    fontSize: theme.typography.sizeXs,
    color: theme.colors.textMuted,
  },
  sourceTag: {
    fontSize: 10,
    fontWeight: theme.typography.weightSemiBold,
    textTransform: 'uppercase',
    color: theme.colors.textMuted,
    backgroundColor: theme.colors.backgroundSubtle,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
  },
});
