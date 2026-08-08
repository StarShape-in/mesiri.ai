import React, { useState } from 'react';
import { Modal, Pressable, Text, TouchableOpacity, View } from 'react-native';
import { Check, ChevronDown, Filter } from 'lucide-react-native';

export interface DropdownFilterOption<T extends string> {
  value: T;
  label: string;
}

interface DropdownFilterProps<T extends string> {
  label: string;
  options: DropdownFilterOption<T>[];
  value: T | null;
  onChange: (value: T | null) => void;
  className?: string;
}

export function DropdownFilter<T extends string>({ label, options, value, onChange, className }: DropdownFilterProps<T>) {
  const [open, setOpen] = useState(false);
  const selected = options.find((o) => o.value === value);

  return (
    <View className={className}>
      <TouchableOpacity
        onPress={() => setOpen(true)}
        activeOpacity={0.75}
        className="flex-row items-center gap-1.5 rounded-full border border-gray-200 bg-white px-3 py-1.5"
      >
        <Filter size={13} color="#3B3B44" strokeWidth={2} />
        <Text className="text-xs font-medium text-gray-700">{selected?.label ?? label}</Text>
        <ChevronDown size={13} color="#6E6E80" strokeWidth={2} />
      </TouchableOpacity>

      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable className="flex-1 bg-black/30 items-center justify-center px-8" onPress={() => setOpen(false)}>
          <View className="w-full max-w-xs gap-1 rounded-2xl bg-white p-2">
            <TouchableOpacity
              onPress={() => { onChange(null); setOpen(false); }}
              className="flex-row items-center justify-between rounded-xl px-3 py-2.5"
            >
              <Text className="text-sm text-gray-700">All</Text>
              {value === null && <Check size={16} color="#E8450F" />}
            </TouchableOpacity>
            {options.map((opt) => (
              <TouchableOpacity
                key={opt.value}
                onPress={() => { onChange(opt.value); setOpen(false); }}
                className="flex-row items-center justify-between rounded-xl px-3 py-2.5"
              >
                <Text className="text-sm text-gray-700">{opt.label}</Text>
                {value === opt.value && <Check size={16} color="#E8450F" />}
              </TouchableOpacity>
            ))}
          </View>
        </Pressable>
      </Modal>
    </View>
  );
}
