import { createContext, useCallback, useContext, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { AlertTriangle, CheckCircle, X } from 'lucide-react';

type ToastKind = 'error' | 'success' | 'info';

interface ToastItem {
  id: number;
  message: string;
  kind: ToastKind;
}

interface ToastContextValue {
  showToast: (message: string, kind?: ToastKind) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const KIND_STYLE: Record<ToastKind, { bg: string; border: string; color: string; Icon: typeof AlertTriangle }> = {
  error: { bg: 'var(--error-soft, #FEE2E2)', border: 'var(--error, #EF4444)', color: 'var(--error, #EF4444)', Icon: AlertTriangle },
  success: { bg: 'var(--primary-soft, #E7F8E1)', border: 'var(--primary, #16A34A)', color: 'var(--primary, #16A34A)', Icon: CheckCircle },
  info: { bg: 'var(--info-soft, #E0F2FE)', border: 'var(--info, #0284C7)', color: 'var(--info, #0284C7)', Icon: CheckCircle },
};

// Errors stay up longer than success/info -- they're usually longer messages
// (a raw DB error, a validation detail) that need actual reading time, not
// a glance.
const DURATION_MS: Record<ToastKind, number> = {
  error: 10000,
  success: 5000,
  info: 5000,
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextId = useRef(0);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback(
    (message: string, kind: ToastKind = 'info') => {
      const id = nextId.current++;
      setToasts((prev) => [...prev, { id, message, kind }]);
      window.setTimeout(() => dismiss(id), DURATION_MS[kind]);
    },
    [dismiss]
  );

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div
        style={{
          position: 'fixed',
          bottom: 'var(--space-6, 24px)',
          right: 'var(--space-6, 24px)',
          zIndex: 1000,
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--space-3, 12px)',
          maxWidth: 420,
        }}
      >
        {toasts.map((t) => {
          const style = KIND_STYLE[t.kind];
          const Icon = style.Icon;
          return (
            <div
              key={t.id}
              role="alert"
              className="animate-fade-in"
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 'var(--space-3, 12px)',
                background: style.bg,
                border: `1px solid ${style.border}`,
                color: style.color,
                borderRadius: 'var(--radius-md, 8px)',
                padding: '12px 14px',
                boxShadow: '0 4px 16px rgba(0,0,0,0.12)',
                fontSize: 13,
                lineHeight: 1.4,
                wordBreak: 'break-word',
              }}
            >
              <Icon size={16} style={{ flexShrink: 0, marginTop: 1 }} />
              <div style={{ flex: 1 }}>{t.message}</div>
              <button
                onClick={() => dismiss(t.id)}
                aria-label="Dismiss"
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'inherit',
                  cursor: 'pointer',
                  padding: 0,
                  display: 'flex',
                  flexShrink: 0,
                  opacity: 0.7,
                }}
              >
                <X size={14} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return ctx;
}

// Axios errors carry the backend's actual message at `err.response.data.detail`
// -- `err.message` alone is just a generic "Request failed with status code
// 500" and throws away the reason the API bothered to send back.
export function getErrorMessage(err: unknown, fallback: string): string {
  if (err && typeof err === 'object' && 'response' in err) {
    const response = (err as { response?: { data?: { detail?: unknown } } }).response;
    const detail = response?.data?.detail;
    if (typeof detail === 'string' && detail.length > 0) {
      return detail;
    }
  }
  if (err instanceof Error && err.message) {
    return err.message;
  }
  return fallback;
}
