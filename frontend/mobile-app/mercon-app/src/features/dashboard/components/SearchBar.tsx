import React from 'react';
import { TextInput, View } from 'react-native';
import { Search } from 'lucide-react-native';

interface SearchBarProps {
  value: string;
  onChangeText: (text: string) => void;
  placeholder?: string;
  onSubmit?: () => void;
  className?: string;
}

export function SearchBar({ value, onChangeText, placeholder = 'Search trips, drivers, vehicles…', onSubmit, className }: SearchBarProps) {
  return (
    <View className={`flex-1 flex-row items-center gap-2 rounded-full bg-gray-100 px-4 py-2.5 ${className ?? ''}`}>
      <Search size={16} color="#6E6E80" strokeWidth={2} />
      <TextInput
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor="#9898A4"
        onSubmitEditing={onSubmit}
        returnKeyType="search"
        className="flex-1 text-sm text-gray-900"
      />
    </View>
  );
}
