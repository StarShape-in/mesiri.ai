import React from 'react';
import { SlidersHorizontal } from 'lucide-react-native';
import { IconButton } from '@/features/dashboard/components';

interface FilterButtonProps {
  onPress?: () => void;
  active?: boolean;
  className?: string;
}

export function FilterButton({ onPress, active, className }: FilterButtonProps) {
  return <IconButton Icon={SlidersHorizontal} onPress={onPress} badge={active} elevated className={className} />;
}
