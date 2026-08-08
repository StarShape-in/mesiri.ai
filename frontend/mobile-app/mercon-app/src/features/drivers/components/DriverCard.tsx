import React from 'react';
import { Text, TouchableOpacity, View } from 'react-native';
import { MapPin, Truck } from 'lucide-react-native';
import { DriverAvatar } from './DriverAvatar';
import { DriverStatusBadge } from './DriverStatusBadge';
import { DriverRating } from './DriverRating';
import { DriverTrips } from './DriverTrips';
import { DriverActionGroup } from './DriverActionGroup';
import { driverFullName, driverInitials, driverLocationLabel } from '../services/driversService';
import type { DriverListItem } from '../types';

interface DriverCardProps {
  driver: DriverListItem;
  onCall?: (driver: DriverListItem) => void;
  onTrack?: (driver: DriverListItem) => void;
  onView?: (driver: DriverListItem) => void;
  className?: string;
}

export function DriverCard({ driver, onCall, onTrack, onView, className }: DriverCardProps) {
  const onTrip = driver.status === 'OnTrip' && !!driver.activeTrip;

  return (
    <View
      className={`gap-4 rounded-3xl border border-[#F3F3F3] bg-white p-5 ${className ?? ''}`}
      style={{ shadowColor: '#000', shadowOffset: { width: 0, height: 6 }, shadowOpacity: 0.05, shadowRadius: 14, elevation: 2 }}
    >
      {/* Header — avatar, name + status, rating/trips */}
      <TouchableOpacity
        activeOpacity={onView ? 0.7 : 1}
        onPress={onView ? () => onView(driver) : undefined}
        className="flex-row items-center gap-3"
      >
        <DriverAvatar initials={driverInitials(driver)} status={driver.status} size={56} />

        <View className="flex-1 gap-1.5">
          <Text numberOfLines={1} className="text-[17px] font-bold text-gray-900">
            {driverFullName(driver)}
          </Text>
          <DriverStatusBadge status={driver.status} />
        </View>

        <View className="items-end gap-1.5">
          <DriverRating rating={driver.rating} />
          <DriverTrips totalTrips={driver.totalTrips} />
        </View>
      </TouchableOpacity>

      {/* Vehicle + location */}
      <View className="gap-2 border-t border-gray-100 pt-4">
        <View className="flex-row items-center gap-2">
          <Truck size={13} color="#9898A4" strokeWidth={2} />
          <Text numberOfLines={1} className="text-[13px] text-gray-500">
            {driver.activeTrip?.vehiclePlate ?? 'Unassigned'}
          </Text>
        </View>
        <View className="flex-row items-center gap-2">
          <MapPin size={13} color="#9898A4" strokeWidth={2} />
          <Text numberOfLines={1} className="text-[13px] text-gray-500">{driverLocationLabel(driver)}</Text>
        </View>
      </View>

      {/* Actions */}
      <DriverActionGroup
        onTrip={onTrip}
        canCall={!!driver.phone}
        onCall={onCall ? () => onCall(driver) : undefined}
        onTrack={onTrack ? () => onTrack(driver) : undefined}
        onView={onView ? () => onView(driver) : undefined}
      />
    </View>
  );
}
