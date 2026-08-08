import React from 'react';
import { View } from 'react-native';
import { SectionHeader } from '@/features/dashboard/components/SectionHeader';

/** Horizontal padding of the screen's scroll content. Bleeding rows offset by this. */
export const SCREEN_PADDING = 16;

/** The app's card surface: 24px radius, hairline border, soft lifted shadow. Matches DashboardMetricCard/DriverCard. */
export const CARD_PADDING = 18;

export const CARD_SHADOW = {
  shadowColor: '#000',
  shadowOffset: { width: 0, height: 8 },
  shadowOpacity: 0.06,
  shadowRadius: 20,
  elevation: 3,
} as const;

interface SectionCardProps {
  children: React.ReactNode;
  /** Set false when the content bleeds to the card edge (e.g. a horizontal list). */
  padded?: boolean;
  className?: string;
}

/** White rounded surface. Titles live *outside* the card — see `Section`. */
export function SectionCard({ children, padded = true, className }: SectionCardProps) {
  return (
    <View
      style={{ ...CARD_SHADOW, ...(padded ? { padding: CARD_PADDING } : { paddingVertical: CARD_PADDING }) }}
      className={`rounded-3xl border border-[#F3F3F3] bg-white ${className ?? ''}`}
    >
      {children}
    </View>
  );
}

interface SectionProps {
  title: string;
  actionLabel?: string;
  onActionPress?: () => void;
  children: React.ReactNode;
}

/**
 * A titled block: header above, card below. Keeping the title out of the card
 * is what the dashboard does and is what gives the screen its Swiss rhythm.
 */
export function Section({ title, actionLabel, onActionPress, children }: SectionProps) {
  return (
    <View className="gap-3">
      <SectionHeader title={title} actionLabel={actionLabel} onActionPress={onActionPress} />
      {children}
    </View>
  );
}
