import React from 'react';
import { ActivityIndicator, Text, TouchableOpacity, View } from 'react-native';
import type { LucideIcon } from 'lucide-react-native';
import { Colors } from '@/theme/tokens';

const BUTTON_HEIGHT = 52;

interface ActionButtonProps {
  label: string;
  Icon: LucideIcon;
  onPress: () => void;
  disabled?: boolean;
  loading?: boolean;
}

/** Orange filled button. `flex-1` so it stays exactly half the row. */
export function PrimaryActionButton({ label, Icon, onPress, disabled, loading }: ActionButtonProps) {
  const inactive = disabled || loading;
  return (
    <TouchableOpacity
      onPress={onPress}
      disabled={inactive}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: !!inactive }}
      activeOpacity={0.85}
      style={{
        height: BUTTON_HEIGHT,
        backgroundColor: Colors.accent,
        shadowColor: Colors.accent,
        shadowOffset: { width: 0, height: 6 },
        shadowOpacity: inactive ? 0 : 0.28,
        shadowRadius: 14,
        elevation: inactive ? 0 : 4,
      }}
      className={`flex-1 flex-row items-center justify-center rounded-2xl px-4 ${inactive ? 'opacity-40' : ''}`}
    >
      {loading ? (
        <ActivityIndicator color={Colors.white} size="small" />
      ) : (
        <>
          <Icon size={17} color={Colors.white} strokeWidth={2.25} />
          <Text numberOfLines={1} className="ml-2 text-[14px] font-bold text-white">
            {label}
          </Text>
        </>
      )}
    </TouchableOpacity>
  );
}

/** White outlined button, same footprint as the primary so the pair stays even. */
export function SecondaryActionButton({ label, Icon, onPress, disabled, loading }: ActionButtonProps) {
  const inactive = disabled || loading;
  return (
    <TouchableOpacity
      onPress={onPress}
      disabled={inactive}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: !!inactive }}
      activeOpacity={0.85}
      style={{ height: BUTTON_HEIGHT }}
      className={`flex-1 flex-row items-center justify-center rounded-2xl border border-[#E4E4E8] bg-white px-4 ${inactive ? 'opacity-40' : ''}`}
    >
      {loading ? (
        <ActivityIndicator color={Colors.gray500} size="small" />
      ) : (
        <>
          <Icon size={17} color={Colors.gray900} strokeWidth={2.25} />
          <Text numberOfLines={1} className="ml-2 text-[14px] font-bold text-gray-900">
            {label}
          </Text>
        </>
      )}
    </TouchableOpacity>
  );
}

/** Equal-width action row. */
export function PrimaryActions({ children }: { children: React.ReactNode }) {
  return <View className="flex-row items-stretch" style={{ gap: 12 }}>{children}</View>;
}
