import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Eye, EyeOff, Loader2, Lock, Mail, ShieldCheck } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { errorMessage } from '../services/api'
import { ErrorAlert } from '../components/primitives'
import { AuthAside } from '../components/AuthAside'

export function LoginPage() {
  const { user, loading, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
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

  const emailValid = /.+@.+\..+/.test(email.trim())
  const passwordReady = password.length >= 8

  return (
    <div className="auth-screen auth-layout">
      <AuthAside mode="login" />

      <div className="auth-main">
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
              <Mail size={13} /> Email
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
              aria-invalid={email.length > 0 && !emailValid}
            />
            {email.length > 0 && !emailValid ? (
              <div className="field-hint bad">Enter a valid email address.</div>
            ) : null}

            <label className="field-label" htmlFor="login-password">
              <Lock size={13} /> Password
            </label>
            <span className="input-wrap">
              <input
                id="login-password"
                className="input"
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                required
                minLength={8}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Your password"
              />
              <button
                type="button"
                className="toggle-eye"
                onClick={() => setShowPassword((value) => !value)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                tabIndex={-1}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </span>
            {password.length > 0 && !passwordReady ? (
              <div className="field-hint bad">Passwords are at least 8 characters.</div>
            ) : (
              <div className="field-hint">Minimum 8 characters.</div>
            )}

            <button
              type="submit"
              className="btn btn-primary btn-block"
              disabled={submitting || (email.length > 0 && !emailValid)}
              style={{ marginTop: 8 }}
            >
              {submitting ? (
                <>
                  <Loader2 size={16} className="spin" /> Signing in…
                </>
              ) : (
                'Sign in'
              )}
            </button>
          </form>

          <p className="muted small" style={{ marginTop: 14 }}>
            No account yet? <Link to="/register">Create one</Link>
          </p>
        </div>
      </div>
    </div>
  )
}
