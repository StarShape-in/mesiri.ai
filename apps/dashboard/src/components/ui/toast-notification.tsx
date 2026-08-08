import * as React from 'react'
import {
  CheckCircle2,
  AlertCircle,
  Info,
  XCircle,
  X,
} from 'lucide-react'

export interface ToastMessage {
  id: string
  type: 'success' | 'error' | 'info' | 'warning'
  title: string
  description?: string
}

interface ToastContextType {
  toasts: ToastMessage[]
  addToast: (toast: Omit<ToastMessage, 'id'>) => void
  removeToast: (id: string) => void
  success: (title: string, description?: string) => void
  error: (title: string, description?: string) => void
  info: (title: string, description?: string) => void
}

const ToastContext = React.createContext<ToastContextType | undefined>(undefined)

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = React.useState<ToastMessage[]>([])

  const removeToast = React.useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const addToast = React.useCallback(
    (toast: Omit<ToastMessage, 'id'>) => {
      const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
      const newToast: ToastMessage = { ...toast, id }
      setToasts((prev) => [...prev.slice(-4), newToast]) // keep max 5 toasts

      // Auto-dismiss after 4 seconds
      setTimeout(() => {
        removeToast(id)
      }, 4000)
    },
    [removeToast]
  )

  const success = React.useCallback(
    (title: string, description?: string) => {
      addToast({ type: 'success', title, description })
    },
    [addToast]
  )

  const error = React.useCallback(
    (title: string, description?: string) => {
      addToast({ type: 'error', title, description })
    },
    [addToast]
  )

  const info = React.useCallback(
    (title: string, description?: string) => {
      addToast({ type: 'info', title, description })
    },
    [addToast]
  )

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast, success, error, info }}>
      {children}
      {/* Floating Toast / Snackbar Stack Container */}
      <div
        aria-live="polite"
        className="fixed bottom-5 right-5 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none p-2"
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`pointer-events-auto p-3.5 rounded-lg border shadow-lg flex items-start gap-3 transition-all transform animate-in slide-in-from-bottom-2 duration-200 text-xs backdrop-blur-md ${
              toast.type === 'success'
                ? 'bg-emerald-950/90 text-emerald-100 border-emerald-500/40 dark:bg-emerald-950/90 dark:text-emerald-100'
                : toast.type === 'error'
                ? 'bg-rose-950/90 text-rose-100 border-rose-500/40 dark:bg-rose-950/90 dark:text-rose-100'
                : 'bg-slate-900/90 text-slate-100 border-slate-700/60 dark:bg-slate-900/90 dark:text-slate-100'
            }`}
          >
            <div className="shrink-0 mt-0.5">
              {toast.type === 'success' && <CheckCircle2 className="size-4 text-emerald-400" />}
              {toast.type === 'error' && <XCircle className="size-4 text-rose-400" />}
              {toast.type === 'info' && <Info className="size-4 text-blue-400" />}
              {toast.type === 'warning' && <AlertCircle className="size-4 text-amber-400" />}
            </div>

            <div className="flex-1 min-w-0">
              <div className="font-semibold text-xs leading-snug">{toast.title}</div>
              {toast.description && (
                <div className="text-[11px] opacity-80 mt-0.5 truncate">{toast.description}</div>
              )}
            </div>

            <button
              onClick={() => removeToast(toast.id)}
              className="text-white/60 hover:text-white shrink-0 p-0.5"
            >
              <X className="size-3.5" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const context = React.useContext(ToastContext)
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider')
  }
  return context
}
