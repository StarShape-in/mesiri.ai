import React from 'react';
import { View } from 'react-native';
import { CircleCheck, Clock, ShieldCheck, Star } from 'lucide-react-native';
import { Colors } from '@/theme/tokens';
import { Section, SectionCard } from './SectionCard';
import { PerformanceMetricCard } from './PerformanceMetricCard';
import { safetyScoreFromRisk } from '../services/driverDetailsService';
import type { DriverPerformance } from '../types';

interface PerformanceSummaryProps {
  performance: DriverPerformance;
}

/**
 * All-time performance.
 *
 * Trips Completed and On-Time Rate are computed from the driver's real trips.
 * Average Rating has no backing column and renders "—". Safety Score is
 * derived from the driver's real `ai_risk_score` (inverted, as that field
 * measures risk rather than safety).
 */
export function PerformanceSummary({ performance }: PerformanceSummaryProps) {
  const safety = safetyScoreFromRisk(performance.aiRiskScore);

  return (
    <Section title="Performance Summary">
      <SectionCard>
        <View className="flex-row flex-wrap justify-between" style={{ rowGap: 22 }}>
          <PerformanceMetricCard
            Icon={CircleCheck}
            value={String(performance.completedTrips)}
            label="Trips Completed"
            caption={`of ${performance.totalTrips} total`}
            tone={Colors.success}
          />
          <PerformanceMetricCard
            Icon={Clock}
            value={performance.onTimeRatePct !== null ? `${performance.onTimeRatePct}%` : '—'}
            label="On-Time Rate"
            caption={
              performance.onTimeSample > 0
                ? `from ${performance.onTimeSample} ${performance.onTimeSample === 1 ? 'trip' : 'trips'}`
                : 'no scheduled trips yet'
            }
            tone={Colors.info}
          />
          <PerformanceMetricCard
            Icon={Star}
            value={performance.averageRating !== null ? performance.averageRating.toFixed(1) : '—'}
            label="Average Rating"
            caption="not yet tracked"
            tone={Colors.accent}
          />
          <PerformanceMetricCard
            Icon={ShieldCheck}
            value={safety !== null ? `${safety}%` : '—'}
            label="Safety Score"
            caption="from AI risk score"
            tone={Colors.purple}
          />
        </View>
      </SectionCard>
    </Section>
  );
}
