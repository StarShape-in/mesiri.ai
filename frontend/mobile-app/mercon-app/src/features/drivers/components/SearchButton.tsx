import React from 'react';
import { Search } from 'lucide-react-native';
import { IconButton } from '@/features/dashboard/components';

interface SearchButtonProps {
  onPress?: () => void;
  className?: string;
}

export function SearchButton({ onPress, className }: SearchButtonProps) {
  return <IconButton Icon={Search} onPress={onPress} elevated className={className} />;
}
