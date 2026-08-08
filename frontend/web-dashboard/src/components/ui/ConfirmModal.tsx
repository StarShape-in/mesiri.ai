import { AlertTriangle } from 'lucide-react';
import Btn from './Btn';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from './dialog';

interface ConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  isDestructive?: boolean;
  isLoading?: boolean;
  children?: React.ReactNode;
}

export default function ConfirmModal({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  isDestructive = false,
  isLoading = false,
  children,
}: ConfirmModalProps) {
  return (
    <Dialog open={isOpen} onOpenChange={(open) => {
      if (!open && !isLoading) onClose();
    }}>
      <DialogContent className="w-full max-w-sm rounded-[24px] p-6 border-black/[0.08] shadow-2xl overflow-hidden [&>button]:right-4 [&>button]:top-4 [&>button]:text-gray-400">
        <div className="flex flex-col items-center text-center mt-2">
          <div className={`w-12 h-12 rounded-lg flex items-center justify-center mb-4 ${
            isDestructive ? 'bg-red-50 text-red-500' : 'bg-amber-50 text-amber-500'
          }`}>
            <AlertTriangle size={24} className="stroke-[2.2]" />
          </div>

          <DialogHeader className="p-0 m-0">
            <DialogTitle className="text-base font-bold text-[#1C1C2E] px-4 leading-tight text-center">
              {title}
            </DialogTitle>
            <DialogDescription className="text-xs text-[#6E6E80] mt-2 font-medium px-2 text-center">
              {message}
            </DialogDescription>
          </DialogHeader>
        </div>

        {/* Custom Form/Inputs Slot */}
        {children && <div className="w-full mt-3">{children}</div>}

        <div className="flex gap-3 mt-6">
          <Btn 
            label={cancelLabel}
            variant="secondary"
            onClick={onClose}
            disabled={isLoading}
            className="flex-1"
          />
          <Btn 
            label={confirmLabel}
            variant={isDestructive ? 'primary' : 'secondary'}
            onClick={onConfirm}
            disabled={isLoading}
            className={`flex-1 ${isDestructive ? 'bg-[#DC2626] hover:bg-[#B91C1C] hover:shadow-red-500/10' : ''}`}
          />
        </div>
      </DialogContent>
    </Dialog>
  );
}
