import React from 'react';
import { Image, Text, View, type ImageSourcePropType } from 'react-native';
import { DriverStatusIndicator } from './DriverStatusIndicator';
import type { DriverDisplayStatus } from '../types';

interface DriverAvatarProps {
  initials: string;
  /** The backend has no driver-photo field yet — pass this once it does; falls back to an initials avatar. */
  imageUri?: ImageSourcePropType;
  status?: DriverDisplayStatus;
  size?: number;
  className?: string;
}

/** Large rounded-square driver photo/initials tile with a bottom-right status dot. */
export function DriverAvatar({ initials, imageUri, status, size = 64, className }: DriverAvatarProps) {
  const radius = Math.round(size * 0.28);
  return (
    <View style={{ width: size, height: size }} className={`relative ${className ?? ''}`}>
      {imageUri ? (
        <Image source={imageUri} resizeMode="cover" style={{ width: size, height: size, borderRadius: radius }} />
      ) : (
        <View
          style={{ width: size, height: size, borderRadius: radius }}
          className="items-center justify-center bg-primary"
        >
          <Text style={{ fontSize: size * 0.32 }} className="font-bold text-white">{initials}</Text>
        </View>
      )}
      {status && (
        <View className="absolute -bottom-1 -right-1">
          <DriverStatusIndicator status={status} size={Math.round(size * 0.24)} />
        </View>
      )}
    </View>
  );
}
