import React from 'react';
import { TouchableOpacity } from 'react-native';
import { ScanLine } from 'lucide-react-native';

interface ScannerButtonProps {
  onPress?: () => void;
  className?: string;
}

export function ScannerButton({ onPress, className }: ScannerButtonProps) {
  return (
    <TouchableOpacity
      onPress={onPress}
      activeOpacity={0.85}
      accessibilityRole="button"
      accessibilityLabel="Scan QR code"
      className={`h-11 w-11 items-center justify-center rounded-full bg-navbg ${className ?? ''}`}
    >
      <ScanLine size={20} color="#FFFFFF" strokeWidth={2} />
    </TouchableOpacity>
  );
}
