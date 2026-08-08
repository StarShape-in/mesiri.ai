import React from 'react';
import { Text, TouchableOpacity, View } from 'react-native';
import { ChevronRight } from 'lucide-react-native';

interface SectionHeaderProps {
  title: string;
  actionLabel?: string;
  onActionPress?: () => void;
  className?: string;
}

export function SectionHeader({ title, actionLabel, onActionPress, className }: SectionHeaderProps) {
  return (
    <View className={`flex-row items-center justify-between ${className ?? ''}`}>
      <Text className="text-base font-bold text-gray-900">{title}</Text>
      {actionLabel && (
        <TouchableOpacity onPress={onActionPress} activeOpacity={0.7} className="flex-row items-center gap-0.5">
          <Text className="text-xs font-semibold text-primary">{actionLabel}</Text>
          <ChevronRight size={14} color="#E8450F" strokeWidth={2.5} />
        </TouchableOpacity>
      )}
    </View>
  );
}
