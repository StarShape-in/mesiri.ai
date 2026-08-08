import React from 'react';
import { Text, TouchableOpacity, View } from 'react-native';
import { DocumentTypeIcon, documentTypeLabel } from '@/features/dashboard/components/DocumentTypeIcon';
import { DriverDocumentStatusBadge } from './DriverDocumentStatusBadge';
import { CARD_SHADOW } from './SectionCard';
import { formatDate } from '../services/driverDetailsService';
import type { DriverDocument } from '../types';

interface DocumentCardProps {
  document: DriverDocument;
  onPress?: (document: DriverDocument) => void;
}

/**
 * One document tile in the horizontal list. Fixed width so the row scrolls
 * predictably; the icon and its colour come from the document's real `DocType`
 * (reusing the dashboard's DocumentTypeIcon rather than a second copy of that map).
 */
export function DocumentCard({ document, onPress }: DocumentCardProps) {
  return (
    <TouchableOpacity
      onPress={() => onPress?.(document)}
      disabled={!onPress}
      accessibilityRole="button"
      accessibilityLabel={`${documentTypeLabel(document.docType)}, ${document.displayStatus}`}
      activeOpacity={0.85}
      style={{ width: 160, padding: 16, ...CARD_SHADOW }}
      className="rounded-3xl border border-[#F3F3F3] bg-white"
    >
      <DocumentTypeIcon docType={document.docType} size={38} />

      <Text numberOfLines={2} className="mt-3 text-[13px] font-bold leading-[17px] text-gray-900">
        {documentTypeLabel(document.docType)}
      </Text>
      <Text numberOfLines={1} className="mt-1 text-[11px] font-medium text-gray-400">
        {document.expiryDate ? formatDate(document.expiryDate) : 'No expiry'}
      </Text>

      <View className="mt-3 flex-row">
        <DriverDocumentStatusBadge status={document.displayStatus} />
      </View>
    </TouchableOpacity>
  );
}
