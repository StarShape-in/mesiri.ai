import React from 'react';
import { View } from 'react-native';
import { RoleChip } from './RoleChip';
import { BranchChip } from './BranchChip';

interface ContextSelectorProps {
  role: string;
  branch?: string | null;
  className?: string;
}

export function ContextSelector({ role, branch, className }: ContextSelectorProps) {
  return (
    <View className={`flex-row items-center gap-2 ${className ?? ''}`}>
      <RoleChip role={role} />
      {branch ? <BranchChip branch={branch} /> : null}
    </View>
  );
}
