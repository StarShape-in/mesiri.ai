import React from 'react';
import { Image, Text, View, type ImageSourcePropType } from 'react-native';
import { OnlineIndicator } from './OnlineIndicator';

interface DriverAvatarProps {
  initials: string;
  /** The backend doesn't have a driver photo field yet — pass this once it does; falls back to an initials avatar. */
  imageUri?: ImageSourcePropType;
  online?: boolean;
  size?: number;
  className?: string;
}

export function DriverAvatar({ initials, imageUri, online, size = 52, className }: DriverAvatarProps) {
  return (
    <View style={{ width: size, height: size }} className={`relative ${className ?? ''}`}>
      {imageUri ? (
        <Image
          source={imageUri}
          resizeMode="cover"
          style={{ width: size, height: size, borderRadius: size / 2 }}
        />
      ) : (
        <View
          style={{ width: size, height: size, borderRadius: size / 2 }}
          className="items-center justify-center bg-primary"
        >
          <Text style={{ fontSize: size * 0.36 }} className="font-bold text-white">
            {initials}
          </Text>
        </View>
      )}
      {online !== undefined && (
        <View className="absolute -bottom-0.5 -right-0.5">
          <OnlineIndicator online={online} size={Math.round(size * 0.28)} />
        </View>
      )}
    </View>
  );
}
