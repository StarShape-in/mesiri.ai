import React from 'react';
import { Text, TouchableOpacity, View } from 'react-native';
import { DocumentTypeIcon, documentTypeLabel } from './DocumentTypeIcon';
import { DocumentStatusBadge } from './DocumentStatusBadge';
import { ExpiryProgressBar } from './ExpiryProgressBar';
import type { DocumentExpiryEntry } from '../types';

function formatExpiryDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function daysRemainingLabel(daysLeft: number): string {
  if (daysLeft < 0) return `Expired ${Math.abs(daysLeft)} ${Math.abs(daysLeft) === 1 ? 'day' : 'days'} ago`;
  if (daysLeft === 0) return 'Expires today';
  return `${daysLeft} ${daysLeft === 1 ? 'day' : 'days'} remaining`;
}

interface DocumentExpiryCardProps {
  document: DocumentExpiryEntry;
  onPress?: (document: DocumentExpiryEntry) => void;
  className?: string;
}

export function DocumentExpiryCard({ document, onPress, className }: DocumentExpiryCardProps) {
  const Wrapper = onPress ? TouchableOpacity : View;
  return (
    <Wrapper
      {...(onPress ? { onPress: () => onPress(document), activeOpacity: 0.85 } : {})}
      className={`gap-3 rounded-3xl border border-[#F3F3F3] bg-white p-[18px] ${className ?? ''}`}
      style={{ shadowColor: '#000', shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.05, shadowRadius: 10, elevation: 2 }}
    >
      <View className="flex-row items-center gap-3">
        <DocumentTypeIcon docType={document.docType} size={44} />

        <View className="flex-1">
          <Text numberOfLines={1} className="text-sm font-bold text-gray-900">
            {documentTypeLabel(document.docType)}
          </Text>
          <Text numberOfLines={1} className="text-xs text-gray-500">{document.subjectLabel}</Text>
          <Text numberOfLines={1} className="mt-0.5 text-[11px] text-gray-400">
            {formatExpiryDate(document.expiryDate)} · {daysRemainingLabel(document.daysLeft)}
          </Text>
        </View>

        <DocumentStatusBadge daysLeft={document.daysLeft} />
      </View>

      <ExpiryProgressBar daysLeft={document.daysLeft} />
    </Wrapper>
  );
}
