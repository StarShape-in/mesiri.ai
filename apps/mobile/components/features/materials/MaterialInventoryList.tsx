import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ActivityIndicator } from 'react-native';
import { useTheme, useStyles } from '../../../src/theme';
import { EmptyState } from '../../ui/EmptyState';
import { materialsService, MaterialStock } from '../../../src/services/materialsService';
import { Package, AlertCircle } from 'lucide-react-native';

type MaterialInventoryListProps = {
  projectId?: string;
  siteId?: string;
  searchQuery: string;
  refreshTrigger: number;
  onRefreshComplete: () => void;
};

export function MaterialInventoryList({
  projectId,
  siteId,
  searchQuery,
  refreshTrigger,
  onRefreshComplete,
}: MaterialInventoryListProps) {
  const { theme } = useTheme();
  const styles = useStyles(createStyles);

  const [inventory, setInventory] = useState<MaterialStock[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function loadInventory() {
      setIsLoading(true);
      setError(null);
      try {
        const res = await materialsService.getInventory({
          project_id: projectId,
          site_id: siteId,
        });
        if (active) {
          setInventory(res);
        }
      } catch (err: any) {
        if (active) {
          setError('Failed to load stock levels');
        }
      } finally {
        if (active) {
          setIsLoading(false);
          onRefreshComplete();
        }
      }
    }

    loadInventory();
    return () => {
      active = false;
    };
  }, [projectId, siteId, refreshTrigger, onRefreshComplete]);

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

  const filteredInventory = searchQuery
    ? inventory.filter((item) =>
        item.materialName.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : inventory;

  if (filteredInventory.length === 0) {
    return (
      <EmptyState
        message="No inventory items found matching the search query."
        Icon={Package}
      />
    );
  }

  return (
    <View style={styles.container}>
      {filteredInventory.map((item, idx) => {
        const isLowStock = item.currentStock <= 0;
        return (
          <View key={`${item.materialName}-${idx}`} style={styles.card}>
            <View style={styles.header}>
              <View style={styles.titleContainer}>
                <Package size={16} color={theme.colors.textSecondary} style={styles.titleIcon} />
                <Text style={styles.materialName} numberOfLines={1}>{item.materialName}</Text>
              </View>
              <Text
                style={[
                  styles.stockValue,
                  isLowStock ? styles.lowStockValue : styles.highStockValue
                ]}
              >
                {item.currentStock} {item.unit}
              </Text>
            </View>

            {/* Breakdown section */}
            <View style={styles.breakdownContainer}>
              <View style={styles.breakdownCol}>
                <Text style={styles.breakdownLabel}>Total Received</Text>
                <Text style={[styles.breakdownValue, styles.receivedValue]}>
                  {item.totalReceived} {item.unit}
                </Text>
              </View>
              <View style={styles.breakdownDivider} />
              <View style={styles.breakdownCol}>
                <Text style={styles.breakdownLabel}>Total Used</Text>
                <Text style={[styles.breakdownValue, styles.usedValue]}>
                  {item.totalUsed} {item.unit}
                </Text>
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
    backgroundColor: theme.colors.backgroundSurface,
    borderWidth: 1,
    borderColor: theme.colors.borderSubtle,
    borderRadius: theme.radius.lg,
    padding: theme.spacing.space4,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  titleContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
    marginRight: 8,
  },
  titleIcon: {
    marginRight: 8,
  },
  materialName: {
    fontSize: theme.typography.sizeSm,
    fontWeight: theme.typography.weightSemiBold,
    color: theme.colors.textPrimary,
    flex: 1,
  },
  stockValue: {
    fontSize: theme.typography.sizeMd,
    fontWeight: theme.typography.weightBold,
  },
  highStockValue: {
    color: theme.colors.statusSuccessForeground,
  },
  lowStockValue: {
    color: theme.colors.statusDangerForeground,
  },
  breakdownContainer: {
    flexDirection: 'row',
    backgroundColor: theme.colors.backgroundSubtle,
    borderRadius: theme.radius.md,
    paddingVertical: 10,
    paddingHorizontal: 8,
  },
  breakdownCol: {
    flex: 1,
    alignItems: 'center',
  },
  breakdownLabel: {
    fontSize: 10,
    fontWeight: theme.typography.weightMedium,
    color: theme.colors.textMuted,
    textTransform: 'uppercase',
    marginBottom: 2,
  },
  breakdownValue: {
    fontSize: theme.typography.sizeSm,
    fontWeight: theme.typography.weightSemiBold,
  },
  receivedValue: {
    color: theme.colors.textSecondary,
  },
  usedValue: {
    color: theme.colors.textSecondary,
  },
  breakdownDivider: {
    width: 1,
    backgroundColor: theme.colors.borderSubtle,
    marginVertical: 4,
  },
});
