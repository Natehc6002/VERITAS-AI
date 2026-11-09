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

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/upload', label: 'Upload', icon: Upload, end: false },
  { to: '/documents', label: 'Documents', icon: FileStack, end: false },
  { to: '/investigations', label: 'Investigations', icon: FolderOpen, end: false },
  { to: '/compare', label: 'Compare', icon: GitCompareArrows, end: false },
]

const PAGE_TITLES: Array<[RegExp, string]> = [
  [/^\/$/, 'Dashboard'],
  [/^\/upload$/, 'Document upload'],
  [/^\/documents$/, 'Document library'],
  [/^\/documents\/.+/, 'Document investigation'],
  [/^\/investigations$/, 'Investigations'],
  [/^\/compare$/, 'Cross-document comparison'],
]

function pageTitle(pathname: string): string {
  const match = PAGE_TITLES.find(([pattern]) => pattern.test(pathname))
  return match ? match[1] : 'VERITAS AI'
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
          <div className="nav-section">Investigation</div>
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
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
          {user ? (
            <div className="sidebar-user">
              <div className="muted small" title={user.email}>
                {user.email}
              </div>
              <button
                type="button"
                className="btn btn-sm btn-ghost"
                onClick={() => {
                  logout()
                  navigate('/login', { replace: true })
                }}
              >
                <LogOut size={14} /> Sign out
              </button>
            </div>
          ) : null}
          <div className="mt-8">v1.2 · rule-based intelligence</div>
        </div>
      </aside>

      <div className="main-area">
        <header className="topbar">
          <div className="topbar-title">
            <Activity size={16} className="dim" />
            <h2>{pageTitle(location.pathname)}</h2>
          </div>
          <div className="topbar-meta">
            Explainable indicators · not automated fraud verdicts
          </div>
        </header>

        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
