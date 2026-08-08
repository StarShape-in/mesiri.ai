import React from 'react';
import { Text, TouchableOpacity, View } from 'react-native';
import { ArrowLeft, SquarePen } from 'lucide-react-native';
import { Colors } from '@/theme/tokens';

interface DriverHeaderProps {
  title?: string;
  onBack: () => void;
  /** Omitted while the driver record is still loading, so Edit can't open an empty form. */
  onEdit?: () => void;
}

/** Navigation header — back + title on the left, Edit on the right. */
export function DriverHeader({ title = 'Driver Details', onBack, onEdit }: DriverHeaderProps) {
  return (
    <View className="h-14 flex-row items-center justify-between px-4">
      <View className="min-w-0 flex-1 flex-row items-center">
        <TouchableOpacity
          onPress={onBack}
          accessibilityRole="button"
          accessibilityLabel="Go back"
          hitSlop={12}
          activeOpacity={0.7}
          className="h-9 w-9 items-center justify-center rounded-full border border-[#EDEDF0] bg-white"
        >
          <ArrowLeft size={18} color={Colors.gray900} strokeWidth={2.25} />
        </TouchableOpacity>
        <Text numberOfLines={1} className="ml-3 flex-1 text-[17px] font-bold text-gray-900">
          {title}
        </Text>
      </View>

      {onEdit && (
        <TouchableOpacity
          onPress={onEdit}
          accessibilityRole="button"
          accessibilityLabel="Edit driver"
          hitSlop={12}
          activeOpacity={0.7}
          className="ml-3 h-9 w-9 items-center justify-center rounded-full border border-[#EDEDF0] bg-white"
        >
          <SquarePen size={16} color={Colors.gray900} strokeWidth={2.25} />
        </TouchableOpacity>
      )}
    </View>
  );
}
