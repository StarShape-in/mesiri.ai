import React, { useState } from 'react';
import { Modal, Pressable, Text, TouchableOpacity, View } from 'react-native';
import { Check, ChevronDown, ListFilter } from 'lucide-react-native';
import { Colors } from '@/theme/tokens';

export interface SortOption<T extends string> {
  value: T;
  label: string;
}

interface SortDropdownProps<T extends string> {
  value: T;
  options: readonly SortOption<T>[];
  onChange: (value: T) => void;
  className?: string;
}

/**
 * Generic sort pill + option sheet. Feature-agnostic: each feature supplies
 * its own option list rather than shipping a second copy of this UI.
 */
export function SortDropdown<T extends string>({ value, options, onChange, className }: SortDropdownProps<T>) {
  const [open, setOpen] = useState(false);
  const selected = options.find((o) => o.value === value) ?? options[0];

  return (
    <View className={className}>
      <TouchableOpacity
        onPress={() => setOpen(true)}
        activeOpacity={0.75}
        accessibilityRole="button"
        accessibilityLabel={`Sort by ${selected?.label ?? ''}`}
        className="flex-row items-center gap-1.5 rounded-full border border-gray-200 bg-white px-3 py-1.5"
      >
        <ListFilter size={13} color={Colors.gray700} strokeWidth={2} />
        <Text className="text-xs font-medium text-gray-700">{selected?.label}</Text>
        <ChevronDown size={13} color={Colors.gray500} strokeWidth={2} />
      </TouchableOpacity>

      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable className="flex-1 items-center justify-center bg-black/30 px-8" onPress={() => setOpen(false)}>
          <View className="w-full max-w-xs gap-1 rounded-2xl bg-white p-2">
            {options.map((opt) => (
              <TouchableOpacity
                key={opt.value}
                onPress={() => { onChange(opt.value); setOpen(false); }}
                className="flex-row items-center justify-between rounded-xl px-3 py-2.5"
              >
                <Text className="text-sm text-gray-700">{opt.label}</Text>
                {value === opt.value && <Check size={16} color={Colors.accent} />}
              </TouchableOpacity>
            ))}
          </View>
        </Pressable>
      </Modal>
    </View>
  );
}
