import React, { useCallback } from 'react';
import { FlatList, Text, View } from 'react-native';
import { FileText } from 'lucide-react-native';
import { Colors } from '@/theme/tokens';
import { EmptyState, ErrorState, SkeletonBlock } from '@/shared/components';
import { Section, SectionCard, SCREEN_PADDING } from './SectionCard';
import { DocumentCard } from './DocumentCard';
import type { DriverDocument } from '../types';

interface DocumentsSectionProps {
  documents: DriverDocument[];
  needsAttention: number;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  onViewAll?: () => void;
  onSelectDocument?: (document: DriverDocument) => void;
}

function DocumentSkeletonRow() {
  return (
    <View className="flex-row" style={{ gap: 12 }}>
      {[0, 1, 2].map((i) => (
        <View
          key={i}
          style={{ width: 160, padding: 16 }}
          className="rounded-3xl border border-[#F3F3F3] bg-white"
        >
          <SkeletonBlock width={38} height={38} radius={19} />
          <View className="mt-3 gap-2">
            <SkeletonBlock width="85%" height={13} />
            <SkeletonBlock width="55%" height={11} />
            <SkeletonBlock width={68} height={20} radius={10} />
          </View>
        </View>
      ))}
    </View>
  );
}

/**
 * Horizontally scrolling list of the driver's compliance documents.
 *
 * The row bleeds past the screen's side padding so cards run to the edge and
 * read as scrollable; the padding is re-applied inside the content container.
 */
export function DocumentsSection({
  documents,
  needsAttention,
  loading,
  error,
  onRetry,
  onViewAll,
  onSelectDocument,
}: DocumentsSectionProps) {
  const renderItem = useCallback(
    ({ item }: { item: DriverDocument }) => <DocumentCard document={item} onPress={onSelectDocument} />,
    [onSelectDocument],
  );

  const bleed = { marginHorizontal: -SCREEN_PADDING };
  const inset = { paddingHorizontal: SCREEN_PADDING, gap: 12 };

  return (
    <Section
      title="Documents"
      actionLabel={documents.length > 0 && onViewAll ? 'View All' : undefined}
      onActionPress={onViewAll}
    >
      {needsAttention > 0 && !loading && !error ? (
        <Text className="-mt-1 text-[12px] font-semibold" style={{ color: Colors.warning }}>
          {needsAttention} {needsAttention === 1 ? 'document needs' : 'documents need'} attention
        </Text>
      ) : null}

      {loading ? (
        <View style={bleed}>
          <View style={{ paddingHorizontal: SCREEN_PADDING }}>
            <DocumentSkeletonRow />
          </View>
        </View>
      ) : error ? (
        <SectionCard>
          <ErrorState message={error} onRetry={onRetry} />
        </SectionCard>
      ) : documents.length === 0 ? (
        <SectionCard>
          <EmptyState
            Icon={FileText}
            title="No documents"
            subtitle="Nothing has been uploaded for this driver yet."
          />
        </SectionCard>
      ) : (
        <FlatList
          horizontal
          style={bleed}
          data={documents}
          keyExtractor={(d) => d.id}
          renderItem={renderItem}
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={inset}
          // The list lives inside the page ScrollView; it scrolls on the other axis so there is no gesture conflict.
          nestedScrollEnabled
        />
      )}
    </Section>
  );
}
