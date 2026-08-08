/**
 * "Document Expiry" dashboard section — replaces Fleet Utilization on the
 * Operator Home screen. Owns its own data via useDocumentExpiry(scope);
 * presentation components never call the API themselves.
 */
import React, { useState } from 'react';
import { View } from 'react-native';
import { CheckCircle2, Clock, FileX2, XCircle } from 'lucide-react-native';
import { EmptyState, ErrorState } from '@/shared/components';
import { SectionHeader } from './SectionHeader';
import { SegmentControl, type SegmentOption } from './SegmentControl';
import { DocumentSummaryCard } from './DocumentSummaryCard';
import { DocumentExpiryCard } from './DocumentExpiryCard';
import { SkeletonDocumentSummaryCard, SkeletonDocumentExpiryCard } from './DocumentExpirySkeletons';
import { useDocumentExpiry } from '../hooks';
import type { DocumentExpiryEntry, DocumentFilterScope } from '../types';

const MAX_ROWS = 5;

const SCOPE_OPTIONS: SegmentOption<DocumentFilterScope>[] = [
  { value: 'all', label: 'All' },
  { value: 'vehicles', label: 'Vehicles' },
  { value: 'drivers', label: 'Drivers' },
  { value: 'company', label: 'Company' },
];

interface DocumentExpirySectionProps {
  onViewAll?: () => void;
  onDocumentPress?: (document: DocumentExpiryEntry) => void;
  className?: string;
}

export function DocumentExpirySection({ onViewAll, onDocumentPress, className }: DocumentExpirySectionProps) {
  const [scope, setScope] = useState<DocumentFilterScope>('all');
  const { summary, documents, loading, error, refresh } = useDocumentExpiry(scope);

  return (
    <View className={`gap-3 ${className ?? ''}`}>
      <SectionHeader title="Document Expiry" actionLabel="View All" onActionPress={onViewAll} />

      {loading ? (
        <View className="flex-row gap-2.5">
          <SkeletonDocumentSummaryCard />
          <SkeletonDocumentSummaryCard />
          <SkeletonDocumentSummaryCard />
        </View>
      ) : error ? (
        <ErrorState message={error} onRetry={() => refresh()} />
      ) : (
        <View className="flex-row gap-2.5">
          <DocumentSummaryCard label="Expiring Soon" count={summary?.expiringSoon ?? 0} Icon={Clock} tone="warning" />
          <DocumentSummaryCard label="Expired" count={summary?.expired ?? 0} Icon={XCircle} tone="danger" />
          <DocumentSummaryCard label="Valid" count={summary?.valid ?? 0} Icon={CheckCircle2} tone="success" />
        </View>
      )}

      <SegmentControl options={SCOPE_OPTIONS} value={scope} onChange={setScope} className="self-start" />

      <View className="gap-2.5">
        {loading ? (
          <>
            <SkeletonDocumentExpiryCard />
            <SkeletonDocumentExpiryCard />
          </>
        ) : error ? null : documents.length === 0 ? (
          <EmptyState title="No documents expiring" subtitle="Everything in this category is up to date." Icon={FileX2} />
        ) : (
          documents.slice(0, MAX_ROWS).map((document) => (
            <DocumentExpiryCard key={document.id} document={document} onPress={onDocumentPress} />
          ))
        )}
      </View>
    </View>
  );
}
