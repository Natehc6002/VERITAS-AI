import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  FileText,
  Image as ImageIcon,
  Info,
  Inbox,
  XCircle,
} from 'lucide-react'
import type { ReactNode } from 'react'

type Tone = 'neutral' | 'accent' | 'success' | 'warning' | 'danger' | 'info'

export function Badge({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  return <span className={`badge badge-${tone}`}>{children}</span>
}

export function StatusBadge({ status }: { status: string }) {
  const tone: Tone =
    status === 'completed'
      ? 'success'
      : status === 'failed'
        ? 'danger'
        : status === 'processing'
          ? 'accent'
          : status === 'no_text'
            ? 'warning'
            : 'neutral'
  const label =
    status === 'no_text'
      ? 'no text layer'
      : status === 'uploaded'
        ? 'uploaded'
        : status.replace('_', ' ')
  return (
    <Badge tone={tone}>
      <span className="badge-dot" />
      {label}
    </Badge>
  )
}

export function SeverityBadge({ severity }: { severity: string }) {
  const tone: Tone =
    severity === 'high'
      ? 'danger'
      : severity === 'medium'
        ? 'warning'
        : severity === 'low'
          ? 'info'
          : 'neutral'
  return <Badge tone={tone}>{severity}</Badge>
}

export function FileIcon({ extension, size = 32 }: { extension: string; size?: number }) {
  const ext = extension.toLowerCase()
  const isImage = ['png', 'jpg', 'jpeg'].includes(ext)
  const style = { width: size, height: size }
  return (
    <span className={`file-icon ${isImage ? 'image' : 'pdf'}`} style={style} aria-hidden>
      {isImage ? <ImageIcon size={size * 0.45} /> : <FileText size={size * 0.45} />}
    </span>
  )
}

export function StatCard({
  icon,
  tone,
  value,
  label,
}: {
  icon: ReactNode
  tone: 'accent' | 'success' | 'warning' | 'danger' | 'info'
  value: ReactNode
  label: string
}) {
  return (
    <div className="stat-card">
      <span className={`stat-icon ${tone}`}>{icon}</span>
      <div>
        <div className="stat-value">{value}</div>
        <div className="stat-label">{label}</div>
      </div>
    </div>
  )
}

export function EmptyState({
  icon,
  title,
  message,
  action,
}: {
  icon?: ReactNode
  title: string
  message: string
  action?: ReactNode
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon">{icon ?? <Inbox size={24} />}</div>
      <h3>{title}</h3>
      <p>{message}</p>
      {action ? <div className="mt-16">{action}</div> : null}
    </div>
  )
}

export function ErrorAlert({
  title = 'Something went wrong',
  message,
  onRetry,
}: {
  title?: string
  message: string
  onRetry?: () => void
}) {
  return (
    <div className="alert alert-error" role="alert">
      <XCircle size={17} />
      <div className="grow">
        <div className="alert-title">{title}</div>
        <div>{message}</div>
      </div>
      {onRetry ? (
        <button type="button" className="btn btn-sm" onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </div>
  )
}

export function InfoAlert({ title, message }: { title: string; message: string }) {
  return (
    <div className="alert alert-info">
      <Info size={17} />
      <div className="grow">
        <div className="alert-title">{title}</div>
        <div>{message}</div>
      </div>
    </div>
  )
}

export function SuccessAlert({ title, message }: { title: string; message: string }) {
  return (
    <div className="alert alert-success">
      <CheckCircle2 size={17} />
      <div className="grow">
        <div className="alert-title">{title}</div>
        <div>{message}</div>
      </div>
    </div>
  )
}

export function WarningAlert({ title, message }: { title: string; message: string }) {
  return (
    <div className="alert alert-warning">
      <AlertTriangle size={17} />
      <div className="grow">
        <div className="alert-title">{title}</div>
        <div>{message}</div>
      </div>
    </div>
  )
}

export function LoadingBlock({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="loading-block">
      <span className="spinner lg" />
      <span>{label}</span>
    </div>
  )
}

export function Collapsible({
  open,
  onToggle,
  children,
  title,
}: {
  open: boolean
  onToggle: () => void
  title: ReactNode
  children: ReactNode
}) {
  return (
    <div className="finding">
      <div className="finding-head" onClick={onToggle} role="button" tabIndex={0}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            onToggle()
          }
        }}
      >
        {open ? <ChevronDown size={16} className="dim" /> : <ChevronRight size={16} className="dim" />}
        <div className="grow">{title}</div>
      </div>
      {open ? <div className="finding-body">{children}</div> : null}
    </div>
  )
}
