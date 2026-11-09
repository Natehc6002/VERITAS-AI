import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { CheckCircle2, Info, XCircle } from 'lucide-react'

type ToastTone = 'success' | 'error' | 'info'

interface ToastItem {
  id: number
  tone: ToastTone
  title: string
  message?: string
}

interface ToastContextValue {
  toast: (tone: ToastTone, title: string, message?: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

const TONE_ICON: Record<ToastTone, typeof Info> = {
  success: CheckCircle2,
  error: XCircle,
  info: Info,
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])
  const nextId = useRef(1)

  const dismiss = useCallback((id: number) => {
    setItems((current) => current.filter((item) => item.id !== id))
  }, [])

  const toast = useCallback(
    (tone: ToastTone, title: string, message?: string) => {
      const id = nextId.current++
      setItems((current) => [...current.slice(-3), { id, tone, title, message }])
      window.setTimeout(() => dismiss(id), 4200)
    },
    [dismiss],
  )

  const value = useMemo(() => ({ toast }), [toast])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-stack" role="status" aria-live="polite">
        {items.map((item) => {
          const Icon = TONE_ICON[item.tone]
          return (
            <div className={`toast ${item.tone}`} key={item.id}>
              <Icon size={17} />
              <div className="grow">
                <div className="t-title">{item.title}</div>
                {item.message ? <div className="t-msg">{item.message}</div> : null}
              </div>
              <button
                type="button"
                className="btn btn-sm btn-ghost"
                style={{ padding: 2 }}
                aria-label="Dismiss"
                onClick={() => dismiss(item.id)}
              >
                <XCircle size={14} />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext)
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider')
  }
  return context
}
