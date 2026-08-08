import React from 'react';
import { Text, TouchableOpacity, View } from 'react-native';
import { Navigation, Package } from 'lucide-react-native';
import { Colors } from '@/theme/tokens';
import { statusLabel } from '@/lib/trips';
import { Section, SectionCard } from './SectionCard';
import { formatCoordinates } from '../services/driverDetailsService';
import type { AssignmentStop, DriverAssignment } from '../types';

interface StopRowProps {
  label: string;
  stop: AssignmentStop | null;
  tone: string;
}

/**
 * TripStop carries only latitude/longitude — there is no address column and no
 * geocoder wired up in this app, so the coordinates are shown as-is rather
 * than resolved into a place name that would be invented.
 */
function StopRow({ label, stop, tone }: StopRowProps) {
  return (
    <View className="flex-row items-center">
      {/* 16px rail keeps the dots and the connector on one vertical axis. */}
      <View className="w-4 items-center">
        <View style={{ width: 9, height: 9, borderRadius: 5, backgroundColor: tone }} />
      </View>
      <View className="min-w-0 flex-1 pl-3">
        {/* letterSpacing as a number: RN does not accept em units. */}
        <Text style={{ letterSpacing: 0.8 }} className="text-[10px] font-semibold uppercase text-gray-400">
          {label}
        </Text>
        <Text numberOfLines={1} className="mt-0.5 text-[13px] font-semibold text-gray-900">
          {stop ? formatCoordinates(stop.lat, stop.lng) : '—'}
        </Text>
      </View>
    </View>
  );
}

interface CurrentAssignmentCardProps {
  assignment: DriverAssignment;
  onTrackTrip: () => void;
}

export function CurrentAssignmentCard({ assignment, onTrackTrip }: CurrentAssignmentCardProps) {
  return (
    <Section title="Current Assignment">
      <SectionCard>
        <View className="flex-row items-center">
          <View
            style={{ backgroundColor: `${Colors.accent}14` }}
            className="h-11 w-11 items-center justify-center rounded-2xl"
          >
            <Package size={19} color={Colors.accent} strokeWidth={2.25} />
          </View>

          <View className="min-w-0 flex-1 pl-3.5">
            <Text numberOfLines={1} className="text-[15px] font-bold text-gray-900">
              {assignment.refId ?? 'Active Trip'}
            </Text>
            <Text numberOfLines={1} className="mt-0.5 text-[12px] text-gray-400">
              {assignment.customerName ?? 'Customer unavailable'} · {assignment.cargoType}
            </Text>
          </View>

          <View style={{ backgroundColor: Colors.infoLight }} className="ml-2 rounded-full px-2.5 py-1">
            <Text style={{ color: Colors.info }} className="text-[10px] font-bold">
              {statusLabel(assignment.status)}
            </Text>
          </View>
        </View>

        {/* Route rail */}
        <View className="mt-4 rounded-2xl bg-[#FAFAFB] p-4">
          <StopRow label="Pickup" stop={assignment.pickup} tone={Colors.success} />
          <View className="w-4 items-center">
            <View style={{ width: 1, height: 18 }} className="bg-[#E4E4E8]" />
          </View>
          <StopRow label="Dropoff" stop={assignment.dropoff} tone={Colors.accent} />
        </View>

        <TouchableOpacity
          onPress={onTrackTrip}
          accessibilityRole="button"
          accessibilityLabel="Track trip"
          activeOpacity={0.85}
          className="mt-4 h-12 flex-row items-center justify-center rounded-2xl border border-[#EDEDF0] bg-white"
        >
          <Navigation size={15} color={Colors.accent} strokeWidth={2.25} />
          <Text className="ml-2 text-[14px] font-bold text-gray-900">Track Trip</Text>
        </TouchableOpacity>
      </SectionCard>
    </Section>
  );
}
