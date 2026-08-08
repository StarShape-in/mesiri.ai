import * as React from 'react';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { motion, AnimatePresence } from 'framer-motion';
import { X } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface KpiModalProps {
  isOpen: boolean;
  onClose: () => void;
  originRect?: DOMRect | null;
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  badge?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  maxWidthClass?: string;
}

export function KpiModal({
  isOpen,
  onClose,
  originRect,
  title,
  subtitle,
  badge,
  children,
  className,
  maxWidthClass = 'sm:max-w-xl',
}: KpiModalProps) {
  // Compute origin offset relative to screen center
  const originOffset = React.useMemo(() => {
    if (!originRect || typeof window === 'undefined') {
      return { x: 0, y: -20, scale: 0.95 };
    }
    const cardCenterX = originRect.left + originRect.width / 2;
    const cardCenterY = originRect.top + originRect.height / 2;
    const windowCenterX = window.innerWidth / 2;
    const windowCenterY = window.innerHeight / 2;

    return {
      x: cardCenterX - windowCenterX,
      y: cardCenterY - windowCenterY,
      scale: Math.max(0.15, Math.min(0.4, originRect.width / 600)),
    };
  }, [originRect, isOpen]);

  return (
    <DialogPrimitive.Root open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <AnimatePresence>
        {isOpen && (
          <DialogPrimitive.Portal forceMount>
            {/* Backdrop Overlay */}
            <DialogPrimitive.Overlay asChild>
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs"
              />
            </DialogPrimitive.Overlay>

            {/* Modal Container */}
            <div className="fixed inset-0 z-50 flex items-center justify-center p-4 overflow-y-auto pointer-events-none">
              <DialogPrimitive.Content asChild>
                <motion.div
                  initial={{
                    opacity: 0,
                    scale: originOffset.scale,
                    x: originOffset.x,
                    y: originOffset.y,
                    borderRadius: '16px',
                  }}
                  animate={{
                    opacity: 1,
                    scale: 1,
                    x: 0,
                    y: 0,
                    borderRadius: '16px',
                  }}
                  exit={{
                    opacity: 0,
                    scale: originOffset.scale,
                    x: originOffset.x,
                    y: originOffset.y,
                    transition: { duration: 0.2, ease: [0.32, 0, 0.67, 0] },
                  }}
                  transition={{
                    type: 'spring',
                    stiffness: 340,
                    damping: 28,
                    mass: 0.8,
                  }}
                  className={cn(
                    'pointer-events-auto relative w-full bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xl overflow-hidden focus:outline-none p-6 text-slate-900 dark:text-slate-100',
                    maxWidthClass,
                    className
                  )}
                >
                  {/* Top Bar Accent */}
                  <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-[#E8450F] via-orange-400 to-amber-500" />

                  {/* Header */}
                  {(title || badge || subtitle) && (
                    <div className="flex items-start justify-between gap-4 pb-4 border-b border-slate-100 dark:border-slate-800">
                      <div className="flex flex-col gap-1 pr-6">
                        <div className="flex items-center gap-2.5 flex-wrap">
                          {typeof title === 'string' ? (
                            <h2 className="text-lg font-extrabold tracking-tight text-slate-900 dark:text-slate-100">
                              {title}
                            </h2>
                          ) : (
                            title
                          )}
                          {badge}
                        </div>
                        {subtitle && (
                          <p className="text-xs text-slate-500 dark:text-slate-400 font-medium">
                            {subtitle}
                          </p>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Close button */}
                  <DialogPrimitive.Close className="absolute right-4 top-4 rounded-lg p-1.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors focus:outline-none">
                    <X className="h-4 w-4" />
                    <span className="sr-only">Close</span>
                  </DialogPrimitive.Close>

                  {/* Content */}
                  <div className="pt-4">{children}</div>
                </motion.div>
              </DialogPrimitive.Content>
            </div>
          </DialogPrimitive.Portal>
        )}
      </AnimatePresence>
    </DialogPrimitive.Root>
  );
}

export default KpiModal;
