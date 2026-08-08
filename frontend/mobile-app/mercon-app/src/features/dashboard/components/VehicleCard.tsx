import React from 'react';
import { Text, TouchableOpacity, View, type ImageSourcePropType } from 'react-native';
import { DriverAvatar } from './DriverAvatar';
import { DriverStatus } from './DriverStatus';
import { RoutePreview } from './RoutePreview';
import { InfoRow } from './InfoRow';
import { StatusBadge } from './StatusBadge';
import type { VehicleCardStatus, TripStatus } from '../types';

export interface VehicleCardDriver {
  initials: string;
  name: string;
  online: boolean;
  imageUri?: ImageSourcePropType;
}

export interface VehicleCardVehicle {
  truckId: string;
  model: string;
  capacityKg: number;
}

export interface VehicleCardRoute {
  originLabel: string;
  destinationLabel: string;
  /** 0-1 position of the truck marker along the route preview. */
  progress?: number;
}

interface VehicleCardProps {
  driver: VehicleCardDriver;
  vehicle: VehicleCardVehicle;
  route: VehicleCardRoute;
  status: VehicleCardStatus;
  lastLocation?: { lat: number; lng: number } | null;
  currentTrip?: { id: string; status: TripStatus };
  onPress?: () => void;
  /** Carousel item width — omit to fill the parent (e.g. a single, non-carousel usage). */
  width?: number;
  className?: string;
}

export function VehicleCard({ driver, vehicle, route, status, onPress, width, className }: VehicleCardProps) {
  const Wrapper = onPress ? TouchableOpacity : View;
  return (
    <Wrapper
      {...(onPress ? { onPress, activeOpacity: 0.85 } : {})}
      style={width ? { width } : undefined}
      className={`gap-4 rounded-3xl border border-[#F3F3F3] bg-white p-5 ${className ?? ''}`}
    >
      {/* Section 1 — driver information */}
      <View className="flex-row items-center gap-3">
        <DriverAvatar initials={driver.initials} imageUri={driver.imageUri} size={52} />
        <View className="flex-1">
          <Text numberOfLines={1} className="text-[18px] font-bold text-gray-900">
            {driver.name}
          </Text>
          <DriverStatus online={driver.online} className="mt-0.5" />
        </View>
      </View>

      {/* Section 2 — live route preview */}
      <RoutePreview originLabel={route.originLabel} destinationLabel={route.destinationLabel} progress={route.progress} height={140} />

      {/* Section 3 — vehicle information */}
      <View className="gap-2.5">
        <InfoRow label="Truck ID" value={vehicle.truckId} />
        <InfoRow label="Model" value={vehicle.model} />
        <InfoRow label="Capacity" value={`${(vehicle.capacityKg / 1000).toFixed(1)} Ton`} />
        <View className="flex-row items-center justify-between">
          <Text className="text-[11px] text-gray-400">Status</Text>
          <StatusBadge status={status} />
        </View>
      </View>
    </Wrapper>
  );
}
