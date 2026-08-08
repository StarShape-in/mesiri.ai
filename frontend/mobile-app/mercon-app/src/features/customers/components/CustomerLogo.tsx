import React from 'react';
import { Image, Text, View, type ImageSourcePropType } from 'react-native';
import { Colors } from '@/theme/tokens';
import { customerInitials } from '../services/customersService';

interface CustomerLogoProps {
  name: string;
  /** The backend has no customer-logo field yet — pass this once it does; falls back to initials. */
  logoUri?: ImageSourcePropType;
  size?: number;
  className?: string;
}

/**
 * Circular company mark. `contain` on the image so a wide wordmark keeps its
 * aspect ratio instead of being cropped to the circle.
 */
export function CustomerLogo({ name, logoUri, size = 48, className }: CustomerLogoProps) {
  const radius = size / 2;

  if (logoUri) {
    return (
      <View
        style={{ width: size, height: size, borderRadius: radius }}
        className={`overflow-hidden border border-[#F0F0F3] bg-white ${className ?? ''}`}
      >
        <Image source={logoUri} resizeMode="contain" style={{ width: size, height: size }} />
      </View>
    );
  }

  return (
    <View
      style={{ width: size, height: size, borderRadius: radius, backgroundColor: `${Colors.accent}14` }}
      className={`items-center justify-center ${className ?? ''}`}
    >
      <Text style={{ fontSize: size * 0.34, color: Colors.accent }} className="font-bold">
        {customerInitials(name)}
      </Text>
    </View>
  );
}
