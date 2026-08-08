import React from 'react';
import { View } from 'react-native';
import {
  BadgeCheck, FileSignature, FileStack, FileText, Receipt, ShieldCheck, TriangleAlert, Truck,
  type LucideIcon,
} from 'lucide-react-native';
import type { DocType } from '../types';

const DOC_TYPE_META: Record<DocType, { label: string; Icon: LucideIcon; color: string; bg: string }> = {
  DriverLicense:       { label: 'Driver License',      Icon: BadgeCheck,     color: '#2563EB', bg: '#EFF6FF' },
  VehicleRegistration: { label: 'Vehicle Registration', Icon: Truck,          color: '#3B3B44', bg: '#F5F5F7' },
  Insurance:           { label: 'Vehicle Insurance',    Icon: ShieldCheck,    color: '#16A34A', bg: '#F0FDF4' },
  POD:                 { label: 'Proof of Delivery',    Icon: FileText,       color: '#7C3AED', bg: '#F5F3FF' },
  CustomsClearance:    { label: 'Customs Clearance',    Icon: FileStack,      color: '#D97706', bg: '#FFFBEB' },
  Waybill:              { label: 'Waybill',              Icon: FileText,       color: '#6E6E80', bg: '#F5F5F7' },
  Contract:             { label: 'Contract',              Icon: FileSignature, color: '#2563EB', bg: '#EFF6FF' },
  Invoice:               { label: 'Invoice',               Icon: Receipt,        color: '#16A34A', bg: '#F0FDF4' },
  Emergency:             { label: 'Emergency Report',      Icon: TriangleAlert, color: '#DC2626', bg: '#FEF2F2' },
};

export function documentTypeLabel(docType: DocType): string {
  return DOC_TYPE_META[docType]?.label ?? docType;
}

interface DocumentTypeIconProps {
  docType: DocType;
  size?: number;
  className?: string;
}

/** Circular icon whose color/glyph is automatic based on the document's real `DocType`. */
export function DocumentTypeIcon({ docType, size = 44, className }: DocumentTypeIconProps) {
  const meta = DOC_TYPE_META[docType] ?? DOC_TYPE_META.Waybill;
  return (
    <View
      style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: meta.bg }}
      className={`items-center justify-center ${className ?? ''}`}
    >
      <meta.Icon size={Math.round(size * 0.45)} color={meta.color} strokeWidth={2} />
    </View>
  );
}
