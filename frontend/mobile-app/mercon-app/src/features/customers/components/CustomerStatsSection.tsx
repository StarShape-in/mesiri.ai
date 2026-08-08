import React from 'react';
import { FlatList, View } from 'react-native';
import { Building2, FileSignature, ReceiptText, Truck } from 'lucide-react-native';
import type { LucideIcon } from 'lucide-react-native';
import { SkeletonBlock } from '@/shared/components';
import { CustomerStatCard } from './CustomerStatCard';
import type { CustomerStats } from '../types';

const CustomerStatCardMemo = React.memo(CustomerStatCard);

const CARD_WIDTH = 150;
const GAP = 12;

interface StatEntry {
  key: string;
  Icon: LucideIcon;
  value: string;
  label: string;
  caption?: string;
}

interface CustomerStatsSectionProps {
  stats: CustomerStats;
  loading: boolean;
  /** Screen padding, re-applied inside the bleeding row. */
  inset: number;
}

function SkeletonTile() {
  return (
    <View style={{ width: CARD_WIDTH, padding: 18 }} className="rounded-[22px] bg-navbg">
      <SkeletonBlock width={44} height={44} radius={16} className="bg-white/10" />
      <View className="mt-5 gap-2">
        <SkeletonBlock width={62} height={26} className="bg-white/10" />
        <SkeletonBlock width="80%" height={12} className="bg-white/10" />
        <SkeletonBlock width={34} height={3} radius={2} className="bg-white/10" />
      </View>
    </View>
  );
}

/**
 * Horizontal KPI rail.
 *
 * "Active Rate Cards" stands where a contracts metric would go: the schema has
 * no Contract entity, and rate cards are the only commercial agreement it
 * models — so the tile is labelled for what it actually counts.
 */
export function CustomerStatsSection({ stats, loading, inset }: CustomerStatsSectionProps) {
  const entries: StatEntry[] = [
    {
      key: 'total',
      Icon: Building2,
      value: String(stats.totalCustomers),
      label: 'Total Customers',
    },
    {
      key: 'rate-cards',
      Icon: FileSignature,
      value: String(stats.activeRateCards),
      label: 'Active Rate Cards',
      caption: 'no contract entity yet',
    },
    {
      key: 'trips',
      Icon: Truck,
      value: String(stats.tripsThisMonth),
      label: 'Trips This Month',
    },
    {
      key: 'bills',
      Icon: ReceiptText,
      value: String(stats.pendingBills),
      label: 'Pending Bills',
      caption: 'pending + overdue',
    },
  ];

  const contentContainerStyle = { paddingHorizontal: inset, gap: GAP };
  const bleed = { marginHorizontal: -inset };

  if (loading) {
    return (
      <View style={bleed}>
        <View className="flex-row" style={contentContainerStyle}>
          <SkeletonTile />
          <SkeletonTile />
        </View>
      </View>
    );
  }

  return (
    <FlatList
      horizontal
      style={bleed}
      data={entries}
      keyExtractor={(e) => e.key}
      renderItem={({ item }) => (
        <CustomerStatCardMemo Icon={item.Icon} value={item.value} label={item.label} caption={item.caption} />
      )}
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={contentContainerStyle}
      nestedScrollEnabled
    />
  );
}
