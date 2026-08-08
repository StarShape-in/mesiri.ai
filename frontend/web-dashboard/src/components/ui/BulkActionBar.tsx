import React from 'react';
import { X } from 'lucide-react';
import { cn } from '@/lib/utils';
import Btn from './Btn';

interface BulkActionBarProps {
  selectedCount: number;
  onClear: () => void;
  children?: React.ReactNode;
  className?: string;
}

export default function BulkActionBar({
  selectedCount,
  onClear,
  children,
  className
}: BulkActionBarProps) {
  if (selectedCount === 0) return null;

  return (
    <div 
      className={cn(
        "fixed bottom-6 left-1/2 -translate-x-1/2 z-50 animate-slide-up",
        "bg-white border border-black/[0.08] shadow-2xl rounded-lg p-2",
        "flex items-center gap-4 transition-all duration-300",
        className
      )}
    >
      <div className="flex items-center gap-3 pl-3 pr-2 border-r border-black/[0.08]">
        <div className="flex items-center justify-center w-6 h-6 rounded-full bg-blue-100 text-blue-700 text-xs font-bold">
          {selectedCount}
        </div>
        <span className="text-sm font-semibold text-[#111]">Items Selected</span>
        <button 
          onClick={onClear}
          className="p-1 rounded-md text-[#6E6E80] hover:text-[#111] hover:bg-black/5 transition-colors ml-1"
          title="Clear Selection"
        >
          <X size={16} />
        </button>
      </div>
      
      <div className="flex items-center gap-2 pr-2">
        {children}
      </div>
    </div>
  );
}
