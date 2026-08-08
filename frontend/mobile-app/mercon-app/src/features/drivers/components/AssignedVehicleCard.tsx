import React from 'react';
import { Text, TouchableOpacity, View } from 'react-native';
import { ChevronRight, Truck } from 'lucide-react-native';
import { Colors } from '@/theme/tokens';
import { CARD_SHADOW } from './SectionCard';
import { formatCapacity } from '../services/driverDetailsService';
import type { AssetStatus, AssignedVehicle } from '../types';

const STATUS_LABEL: Record<AssetStatus, string> = {
  Available: 'Available',
  OnTrip: 'On Trip',
  Maintenance: 'Maintenance',
  Inactive: 'Inactive',
};

/** Tuned for the dark surface — the light-background chips would not read here. */
const STATUS_TONE: Record<AssetStatus, string> = {
  Available: '#4ADE80',
  OnTrip: '#FF7A5C',
  Maintenance: '#FBBF24',
  Inactive: '#9CA3AF',
};

interface AssignedVehicleCardProps {
  vehicle: AssignedVehicle;
  onViewVehicle: () => void;
}

/**
 * Dark card showing the vehicle the driver is currently on.
 *
 * The caller hides this entirely when there is no assigned vehicle — a driver
 * has no standing vehicle relation in the schema, only whatever is on their
 * active trip.
 */
export function AssignedVehicleCard({ vehicle, onViewVehicle }: AssignedVehicleCardProps) {
  return (
    <TouchableOpacity
      onPress={onViewVehicle}
      activeOpacity={0.9}
      accessibilityRole="button"
      accessibilityLabel={`View vehicle ${vehicle.plateNumber}`}
      style={{ padding: 18, backgroundColor: Colors.darkCard, ...CARD_SHADOW }}
      className="flex-row items-center rounded-3xl"
    >
      <View
        style={{ backgroundColor: 'rgba(255,255,255,0.08)' }}
        className="h-12 w-12 items-center justify-center rounded-2xl"
      >
        <Truck size={21} color={Colors.white} strokeWidth={2} />
      </View>

      <View className="min-w-0 flex-1 pl-4">
        {/* letterSpacing as a number: RN does not accept em units. */}
        <Text style={{ letterSpacing: 0.8 }} className="text-[10px] font-semibold uppercase text-white/45">
          Assigned Vehicle
        </Text>
        <Text numberOfLines={1} className="mt-1 text-[17px] font-bold leading-[21px] text-white">
          {vehicle.plateNumber}
        </Text>
        <View className="mt-1.5 flex-row items-center">
          <View
            style={{ backgroundColor: `${STATUS_TONE[vehicle.status]}20` }}
            className="rounded-full px-2 py-0.5"
          >
            <Text style={{ color: STATUS_TONE[vehicle.status] }} className="text-[10px] font-bold">
              {STATUS_LABEL[vehicle.status]}
            </Text>
          </View>
          <Text numberOfLines={1} className="ml-2 flex-1 text-[12px] text-white/55">
            {vehicle.assetType} · {formatCapacity(vehicle.capacityKg)}
          </Text>
        </View>
      </View>

      <View
        style={{ backgroundColor: 'rgba(255,255,255,0.08)' }}
        className="ml-2 h-8 w-8 items-center justify-center rounded-full"
      >
        <ChevronRight size={17} color={Colors.white} strokeWidth={2.5} />
      </View>
    </TouchableOpacity>
  );
}
