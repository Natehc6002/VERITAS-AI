import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  Activity,
  FolderOpen,
  FileStack,
  GitCompareArrows,
  LayoutDashboard,
  LogOut,
  ShieldCheck,
  Upload,
} from 'lucide-react'
import { analysisApi } from '../services/api'
import { useAuth } from '../context/AuthContext'

interface NavEntry {
  to: string
  label: string
  icon: typeof LayoutDashboard
  end?: boolean
}

const NAV_SECTIONS: Array<{ title: string; items: NavEntry[] }> = [
  {
    title: 'Workspace',
    items: [
      { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
      { to: '/upload', label: 'Upload', icon: Upload },
      { to: '/documents', label: 'Documents', icon: FileStack },
    ],
  },
  {
    title: 'Intelligence',
    items: [
      { to: '/compare', label: 'Comparison', icon: GitCompareArrows },
      { to: '/investigations', label: 'Investigations', icon: FolderOpen },
    ],
  },
]

const PAGE_TITLES: Array<[RegExp, string, string]> = [
  [/^\/$/, 'Dashboard', 'Overview'],
  [/^\/upload$/, 'Document upload', 'Ingestion'],
  [/^\/documents$/, 'Document library', 'Evidence store'],
  [/^\/documents\/.+/, 'Document investigation', 'Analysis workspace'],
  [/^\/investigations$/, 'Investigations', 'Case files'],
  [/^\/compare$/, 'Cross-document comparison', 'Correlation'],
]

function pageMeta(pathname: string): [string, string] {
  const match = PAGE_TITLES.find(([pattern]) => pattern.test(pathname))
  return match ? [match[1], match[2]] : ['VERITAS AI', '']
}

function initials(email: string): string {
  const part = email.split('@')[0] || '?'
  const words = part.split(/[._-]+/).filter(Boolean)
  if (words.length >= 2) return (words[0][0] + words[1][0]).slice(0, 2)
  return part.slice(0, 2)
}

export function AppShell() {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const [backendStatus, setBackendStatus] = useState<'checking' | 'online' | 'offline'>('checking')

  useEffect(() => {
    let cancelled = false
    analysisApi
      .health()
      .then(() => !cancelled && setBackendStatus('online'))
      .catch(() => !cancelled && setBackendStatus('offline'))
    return () => {
      cancelled = true
    }
  }, [location.pathname])

  const [title, kicker] = pageMeta(location.pathname)
  const statusLabel =
    backendStatus === 'online'
      ? 'Backend online'
      : backendStatus === 'offline'
        ? 'Backend offline'
        : 'Checking…'

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="brand-mark">
            <ShieldCheck size={19} />
          </span>
          <div>
            <div className="brand-name">VERITAS AI</div>
            <div className="brand-sub">Document forensics</div>
          </div>
        </div>

        <nav className="sidebar-nav" aria-label="Primary">
          {NAV_SECTIONS.map((section) => (
            <div key={section.title}>
              <div className="nav-section">{section.title}</div>
              {section.items.map(({ to, label, icon: Icon, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
                >
                  <Icon size={17} />
                  {label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        <div className="sidebar-foot">
          <div className="flex" style={{ gap: 7 }}>
            <span
              className="badge-dot"
              style={{
                background:
                  backendStatus === 'online'
                    ? 'var(--success)'
                    : backendStatus === 'offline'
                      ? 'var(--danger)'
                      : 'var(--warning)',
              }}
            />
            <span>
              {backendStatus === 'online'
                ? 'Backend connected'
                : backendStatus === 'offline'
                  ? 'Backend unreachable'
                  : 'Checking backend…'}
            </span>
          </div>
          <div className="mt-8">v1.2 · rule-based intelligence</div>
        </div>
      </aside>

      <div className="main-area">
        <header className="topbar">
          <div className="topbar-title">
            <Activity size={16} className="dim" />
            <div style={{ minWidth: 0 }}>
              <h2>{title}</h2>
              {kicker ? <div className="topbar-meta">{kicker}</div> : null}
            </div>
          </div>

          <div className="flex flex-wrap" style={{ gap: 12, justifyContent: 'flex-end' }}>
            <span
              className={`status-pill ${backendStatus}`}
              title={`API health: ${statusLabel}`}
            >
              <span className="badge-dot" />
              <span className="label-full">{statusLabel}</span>
            </span>

            {user ? (
              <div className="topbar-user">
                <span className="avatar" aria-hidden>
                  {initials(user.email)}
                </span>
                <div className="who">
                  <span className="name" title={user.email}>
                    {user.email}
                  </span>
                  <span className="role">Investigator</span>
                </div>
                <button
                  type="button"
                  className="btn btn-sm btn-ghost"
                  title="Sign out"
                  aria-label="Sign out"
                  onClick={() => {
                    logout()
                    navigate('/login', { replace: true })
                  }}
                >
                  <LogOut size={15} />
                </button>
              </div>
            ) : null}
          </div>
        </header>

        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
