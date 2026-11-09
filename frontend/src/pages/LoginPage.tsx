import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ShieldCheck } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { errorMessage } from '../services/api'
import { ErrorAlert } from '../components/primitives'

export function LoginPage() {
  const { user, loading, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (!loading && user) {
    const redirectTo = (location.state as { from?: string } | null)?.from ?? '/'
    return <Navigate to={redirectTo} replace />
  }

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await login(email.trim(), password)
      navigate('/', { replace: true })
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="auth-screen">
      <div className="auth-card card">
        <div className="sidebar-brand" style={{ marginBottom: 18 }}>
          <span className="brand-mark">
            <ShieldCheck size={19} />
          </span>
          <div>
            <div className="brand-name">VERITAS AI</div>
            <div className="brand-sub">Document forensics</div>
          </div>
        </div>
        <h1 style={{ fontSize: 20, marginBottom: 4 }}>Sign in</h1>
        <p className="subtitle" style={{ marginBottom: 16 }}>
          Access your investigations, documents and forensic reports.
        </p>

        {error ? <ErrorAlert title="Sign-in failed" message={error} /> : null}

        <form onSubmit={onSubmit} className="auth-form">
          <label className="field-label" htmlFor="login-email">
            Email
          </label>
          <input
            id="login-email"
            className="input"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@example.com"
          />

          <label className="field-label" htmlFor="login-password">
            Password
          </label>
          <input
            id="login-password"
            className="input"
            type="password"
            autoComplete="current-password"
            required
            minLength={8}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Your password"
          />

          <button
            type="submit"
            className="btn btn-primary btn-block"
            disabled={submitting}
            style={{ marginTop: 8 }}
          >
            {submitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <p className="muted small" style={{ marginTop: 14 }}>
          No account yet? <Link to="/register">Create one</Link>
        </p>
      </div>
    </div>
  )
}
