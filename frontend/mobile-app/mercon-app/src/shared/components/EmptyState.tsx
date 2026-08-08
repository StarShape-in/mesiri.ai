import React from 'react';
import { Text, View } from 'react-native';
import type { LucideIcon } from 'lucide-react-native';
import { Inbox } from 'lucide-react-native';

interface EmptyStateProps {
  title: string;
  subtitle?: string;
  Icon?: LucideIcon;
  className?: string;
}

export function EmptyState({ title, subtitle, Icon = Inbox, className }: EmptyStateProps) {
  return (
    <View className={`items-center gap-2 py-8 px-4 ${className ?? ''}`}>
      <Icon size={26} color="#9898A4" strokeWidth={1.75} />
      <Text className="text-center text-sm font-semibold text-gray-700">{title}</Text>
      {subtitle ? <Text className="text-center text-xs text-gray-500">{subtitle}</Text> : null}
    </View>
  );
}
