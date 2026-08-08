import type { DocType } from '@/services/documentService';

/** Human-friendly label for each DocType enum value. */
const DOC_TYPE_LABELS: Record<DocType, string> = {
  DriverLicense:       'Driver License',
  VehicleRegistration: 'Vehicle Registration',
  Insurance:           'Insurance',
  POD:                 'Proof of Delivery',
  CustomsClearance:    'Customs Clearance',
  Waybill:             'Waybill',
  Contract:            'Contract',
  Invoice:             'Invoice',
};

export function docTypeLabel(t: string): string {
  return DOC_TYPE_LABELS[t as DocType] ?? t;
}

export type DocCategory = 'Drivers' | 'Vehicles' | 'Company' | 'Operations';

/** Map a document's owning entity_type to a UI category. */
export function categoryForEntity(entityType: string): DocCategory {
  switch (entityType) {
    case 'Driver': return 'Drivers';
    case 'Vehicle':
    case 'MaintenanceRecord': return 'Vehicles';
    case 'Trip': return 'Operations';
    default: return 'Company';
  }
}

/** Map a DocType to a UI category (each doc type belongs to exactly one). */
export function categoryForDocType(t: string): DocCategory {
  switch (t as DocType) {
    case 'DriverLicense': return 'Drivers';
    case 'VehicleRegistration':
    case 'Insurance': return 'Vehicles';
    case 'POD':
    case 'Waybill':
    case 'CustomsClearance': return 'Operations';
    case 'Contract':
    case 'Invoice': return 'Company';
    default: return 'Company';
  }
}

/** Whole days from now until the given ISO date (negative = already past). */
export function daysUntil(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return null;
  return Math.ceil((then - Date.now()) / (1000 * 60 * 60 * 24));
}
