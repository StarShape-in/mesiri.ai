import React from 'react';
import { Text, TouchableOpacity, View } from 'react-native';

export interface SegmentOption<T extends string> {
  value: T;
  label: string;
}

interface SegmentControlProps<T extends string> {
  options: SegmentOption<T>[];
  value: T;
  onChange: (value: T) => void;
  className?: string;
}

export function SegmentControl<T extends string>({ options, value, onChange, className }: SegmentControlProps<T>) {
  return (
    <View className={`flex-row rounded-full bg-gray-100 p-1 ${className ?? ''}`}>
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <TouchableOpacity
            key={opt.value}
            onPress={() => onChange(opt.value)}
            activeOpacity={0.8}
            className={`rounded-full px-3 py-1.5 ${active ? 'bg-white' : ''}`}
            style={active ? { shadowColor: '#000', shadowOpacity: 0.08, shadowRadius: 3, shadowOffset: { width: 0, height: 1 }, elevation: 1 } : undefined}
          >
            <Text className={`text-xs font-semibold ${active ? 'text-gray-900' : 'text-gray-500'}`}>
              {opt.label}
            </Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}
