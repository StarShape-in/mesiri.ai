import React from 'react';
import { Text, View } from 'react-native';
import { Building2 } from 'lucide-react-native';

interface BranchChipProps {
  branch: string;
  className?: string;
}

/** Presentational only — the backend has no branch/location concept yet, so callers must supply a real value. */
export function BranchChip({ branch, className }: BranchChipProps) {
  return (
    <View className={`flex-row items-center gap-1.5 rounded-full bg-gray-100 px-3 py-1.5 ${className ?? ''}`}>
      <Building2 size={13} color="#3B3B44" strokeWidth={2.2} />
      <Text className="text-xs font-semibold text-gray-700">{branch}</Text>
    </View>
  );
}
