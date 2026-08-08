import React from 'react';
import { Image, Text, View } from 'react-native';
import { NotificationButton } from './NotificationButton';

interface AppHeaderProps {
  logoSource: number;
  logoSize?: number;
  greeting: string;
  userName: string;
  unreadNotifications: number;
  onNotificationPress?: () => void;
  className?: string;
}

export function AppHeader({
  logoSource, logoSize = 48, greeting, userName, unreadNotifications, onNotificationPress, className,
}: AppHeaderProps) {
  return (
    <View className={`flex-row items-center justify-between ${className ?? ''}`}>
      <View className="flex-row items-center gap-3">
        <Image
          source={logoSource}
          resizeMode="contain"
          className="rounded-xl"
          style={{ width: logoSize, height: logoSize }}
        />
        <View>
          <Text className="text-xs text-gray-500">{greeting}</Text>
          <Text className="text-lg font-extrabold text-gray-900">{userName}</Text>
        </View>
      </View>
      <NotificationButton unreadCount={unreadNotifications} onPress={onNotificationPress} />
    </View>
  );
}
