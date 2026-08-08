import React from 'react';
import { Text, View } from 'react-native';
import type { LucideIcon } from 'lucide-react-native';
import { BadgeCheck, CalendarClock, Hash, IdCard, Phone } from 'lucide-react-native';
import { Colors } from '@/theme/tokens';
import { Section, SectionCard } from './SectionCard';
import { formatDate, formatDaysLeft } from '../services/driverDetailsService';
import type { DriverDetail } from '../types';

interface FieldProps {
  Icon: LucideIcon;
  label: string;
  value: string;
  /** Optional second line, e.g. "12 days left" under an expiry date. */
  hint?: string;
  hintTone?: 'muted' | 'warning' | 'danger';
}

const HINT_COLOR = {
  muted: Colors.gray400,
  warning: Colors.warning,
  danger: Colors.danger,
} as const;

/**
 * One labelled field, fixed to just under half the row so the grid stays a
 * clean two columns — a lone trailing field sits left rather than stretching.
 */
function Field({ Icon, label, value, hint, hintTone = 'muted' }: FieldProps) {
  return (
    <View style={{ width: '48%' }}>
      <View className="flex-row items-center gap-1.5">
        <Icon size={12} color={Colors.gray400} strokeWidth={2} />
        {/* letterSpacing as a number: RN does not accept em units. */}
        <Text
          numberOfLines={1}
          style={{ letterSpacing: 0.5 }}
          className="text-[11px] font-medium uppercase text-gray-400"
        >
          {label}
        </Text>
      </View>
      <Text numberOfLines={1} className="mt-1.5 text-[14px] font-semibold text-gray-900">
        {value}
      </Text>
      {hint ? (
        <Text numberOfLines={1} className="mt-0.5 text-[11px] font-medium" style={{ color: HINT_COLOR[hintTone] }}>
          {hint}
        </Text>
      ) : null}
    </View>
  );
}

interface ContactInformationCardProps {
  driver: DriverDetail;
}

/**
 * Contact and licence details.
 *
 * Only fields the backend actually stores are rendered. The Driver model has
 * no email, nationality, licence *type*, emergency contact, blood group,
 * languages or years-of-experience column — those are omitted rather than
 * shown as permanently empty rows. Adding them is a schema change, not a UI one.
 */
export function ContactInformationCard({ driver }: ContactInformationCardProps) {
  const licenceExpired = driver.licenseDaysLeft < 0;
  const licenceSoon = !licenceExpired && driver.licenseDaysLeft <= 30;

  return (
    <Section title="Contact Information">
      <SectionCard>
        <View className="flex-row flex-wrap justify-between" style={{ rowGap: 18 }}>
          <Field Icon={Phone} label="Phone" value={driver.phone ?? '—'} />
          <Field Icon={Hash} label="Driver ID" value={driver.refId ?? '—'} />
          <Field Icon={IdCard} label="License No." value={driver.licenseNumber} />
          <Field
            Icon={CalendarClock}
            label="License Expiry"
            value={formatDate(driver.licenseExpiry)}
            hint={formatDaysLeft(driver.licenseDaysLeft)}
            hintTone={licenceExpired ? 'danger' : licenceSoon ? 'warning' : 'muted'}
          />
          <Field Icon={BadgeCheck} label="Joined" value={formatDate(driver.createdAt)} />
        </View>
      </SectionCard>
    </Section>
  );
}
