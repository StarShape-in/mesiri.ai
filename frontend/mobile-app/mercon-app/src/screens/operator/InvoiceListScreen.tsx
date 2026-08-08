import React, { useMemo, useState } from 'react';
import {
  View, Text, ScrollView, StyleSheet, SafeAreaView,
  StatusBar, FlatList, ActivityIndicator, RefreshControl, Alert,
} from 'react-native';
import {
  FileText, Hourglass, Siren, Wallet, Truck, Calendar, Clock, type LucideIcon,
} from 'lucide-react-native';
import { Colors, Spacing, Radius, Typography, Shadows } from '../../theme/tokens';
import { StatusBadge, SearchInput, FilterChip, Button } from '../../components';
import { getApiErrorMessage } from '../../lib/api';
import { operatorService, useOperatorInvoices, type OperatorInvoice } from '../../lib/operator';

const FILTERS = ['All', 'Pending', 'Paid', 'Overdue', 'Draft', 'Cancelled'];

function money(currency: string, n: number): string {
  return `${currency} ${Math.round(n).toLocaleString()}`;
}

function formatDate(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' });
}

const InvoiceCard = ({ item, onMarkPaid }: { item: OperatorInvoice; onMarkPaid: (id: string) => void }) => {
  const [marking, setMarking] = useState(false);
  const canMarkPaid = item.status === 'Pending' || item.status === 'Overdue';

  const handleMarkPaid = () => {
    Alert.alert('Mark as Paid', `Mark invoice ${item.ref_id ?? item.id.slice(0, 8)} as paid?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Mark Paid',
        onPress: async () => {
          setMarking(true);
          try {
            await operatorService.updateInvoiceStatus(item.id, 'Paid');
            onMarkPaid(item.id);
          } catch (e) {
            Alert.alert('Could not update invoice', getApiErrorMessage(e));
          } finally {
            setMarking(false);
          }
        },
      },
    ]);
  };

  return (
    <View style={styles.card}>
      <View style={styles.cardTop}>
        <View>
          <Text style={styles.invoiceId}>{item.ref_id ?? item.id.slice(0, 8)}</Text>
          <Text style={styles.customer}>{item.customer?.name ?? 'Customer'}</Text>
        </View>
        <View style={styles.amountCol}>
          <Text style={styles.amount}>{money(item.currency, item.total_amount)}</Text>
          <StatusBadge status={item.status} />
        </View>
      </View>
      <View style={styles.cardMeta}>
        {item.trip?.ref_id ? (
          <View style={styles.metaItem}>
            <Truck size={13} color={Colors.gray500} strokeWidth={2} />
            <Text style={styles.metaText}>{item.trip.ref_id}</Text>
          </View>
        ) : null}
        <View style={styles.metaItem}>
          <Calendar size={13} color={Colors.gray500} strokeWidth={2} />
          <Text style={styles.metaText}>Issued: {formatDate(item.createdAt)}</Text>
        </View>
        <View style={styles.metaItem}>
          <Clock size={13} color={item.status === 'Overdue' ? Colors.error : Colors.gray500} strokeWidth={2} />
          <Text style={[styles.metaText, item.status === 'Overdue' ? styles.overdueText : null]}>
            Due: {formatDate(item.due_date)}
          </Text>
        </View>
      </View>
      {canMarkPaid && (
        <Button
          variant="success"
          size="sm"
          label={marking ? 'Marking…' : 'Mark as Paid'}
          loading={marking}
          onPress={handleMarkPaid}
        />
      )}
    </View>
  );
};

const InvoiceListScreen = () => {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('All');
  const { invoices, loading, error, refetch } = useOperatorInvoices();

  const totalValue = invoices.reduce((sum, i) => sum + i.total_amount, 0);
  const count = (status: string) => invoices.filter((i) => i.status === status).length;

  const STAT_CARDS: { label: string; value: string; Icon: LucideIcon; color: string }[] = [
    { label: 'Total Invoices', value: String(invoices.length), Icon: FileText, color: Colors.gray900 },
    { label: 'Pending', value: String(count('Pending')), Icon: Hourglass, color: Colors.warning },
    { label: 'Overdue', value: String(count('Overdue')), Icon: Siren, color: Colors.error },
    { label: 'Total Value', value: `SAR ${(totalValue / 1000).toFixed(0)}K`, Icon: Wallet, color: Colors.success },
  ];

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return invoices.filter((inv) => {
      if (statusFilter !== 'All' && inv.status !== statusFilter) return false;
      if (!q) return true;
      return (
        (inv.ref_id ?? '').toLowerCase().includes(q) ||
        (inv.customer?.name ?? '').toLowerCase().includes(q) ||
        (inv.trip?.ref_id ?? '').toLowerCase().includes(q)
      );
    });
  }, [invoices, statusFilter, search]);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.gray100 }}>
      <StatusBar barStyle="dark-content" backgroundColor={Colors.white} />
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Invoices</Text>
      </View>

      {/* Stat Cards */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.statsRow}>
        {STAT_CARDS.map((s) => (
          <View key={s.label} style={styles.statCard}>
            <s.Icon size={20} color={s.color} strokeWidth={2} />
            <Text style={[styles.statValue, { color: s.color }]}>{s.value}</Text>
            <Text style={styles.statLabel}>{s.label}</Text>
          </View>
        ))}
      </ScrollView>

      <SearchInput
        value={search}
        onChangeText={setSearch}
        placeholder="Search invoices, customers..."
        style={styles.search}
      />

      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filtersRow}>
        {FILTERS.map((f) => (
          <FilterChip
            key={f}
            label={f}
            active={statusFilter === f}
            onPress={() => setStatusFilter(f)}
          />
        ))}
      </ScrollView>

      <FlatList
        data={filtered}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={loading && invoices.length > 0} onRefresh={refetch} />}
        renderItem={({ item }) => <InvoiceCard item={item} onMarkPaid={() => refetch()} />}
        ListEmptyComponent={
          loading ? (
            <ActivityIndicator color={Colors.primary} style={{ marginTop: Spacing['3xl'] }} />
          ) : (
            <View style={styles.empty}>
              <FileText size={44} color={Colors.gray400} strokeWidth={1.6} />
              <Text style={styles.emptyText}>{error ?? 'No invoices found'}</Text>
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
    alignItems: 'center',
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
  statsRow: {
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    gap: Spacing.sm,
  },
  statCard: {
    backgroundColor: Colors.white,
    borderRadius: Radius.xl,
    padding: Spacing.md,
    alignItems: 'center',
    minWidth: 90,
    ...Shadows.sm,
    gap: 2,
  },
  statIcon: {
    fontSize: 20,
  },
  statValue: {
    fontSize: Typography.lg,
    fontWeight: '800',
  },
  statLabel: {
    fontSize: Typography.xs,
    color: Colors.gray500,
    textAlign: 'center',
  },
  search: {
    marginHorizontal: Spacing.lg,
    marginBottom: Spacing.xs,
  },
  filtersRow: {
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.sm,
    gap: Spacing.xs,
  },
  list: {
    padding: Spacing.lg,
    gap: Spacing.md,
    paddingBottom: 100,
    flexGrow: 1,
  },
  card: {
    backgroundColor: Colors.white,
    borderRadius: Radius.xl,
    padding: Spacing.lg,
    ...Shadows.sm,
    gap: Spacing.md,
  },
  cardTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  invoiceId: {
    fontSize: Typography.sm,
    fontWeight: '800',
    color: Colors.gray900,
  },
  customer: {
    fontSize: Typography.xs,
    color: Colors.gray600,
    marginTop: 2,
  },
  amountCol: {
    alignItems: 'flex-end',
    gap: Spacing.xs,
  },
  amount: {
    fontSize: Typography.base,
    fontWeight: '800',
    color: Colors.gray900,
  },
  cardMeta: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.sm,
  },
  metaItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  metaText: {
    fontSize: Typography.xs,
    color: Colors.gray500,
  },
  overdueText: {
    color: Colors.error,
    fontWeight: '700',
  },
  empty: {
    alignItems: 'center',
    paddingTop: Spacing['3xl'],
    gap: Spacing.sm,
  },
  emptyIcon: {
    fontSize: 40,
  },
  emptyText: {
    fontSize: Typography.base,
    color: Colors.gray500,
  },
});

export default InvoiceListScreen;
