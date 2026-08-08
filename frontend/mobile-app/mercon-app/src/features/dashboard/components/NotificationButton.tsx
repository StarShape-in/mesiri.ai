import React from 'react';
import { Bell } from 'lucide-react-native';
import { IconButton } from './IconButton';

interface NotificationButtonProps {
  unreadCount: number;
  onPress?: () => void;
  className?: string;
}

export function NotificationButton({ unreadCount, onPress, className }: NotificationButtonProps) {
  return <IconButton Icon={Bell} onPress={onPress} badge={unreadCount > 0} className={className} />;
}
