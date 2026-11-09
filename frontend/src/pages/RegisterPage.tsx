import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { ShieldCheck } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { errorMessage } from '../services/api'
import { ErrorAlert } from '../components/primitives'

export function RegisterPage() {
  const { user, loading, register } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (!loading && user) {
    return <Navigate to="/" replace />
  }

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    if (password !== confirm) {
      setError('Passwords do not match.')
      return
    }
    setSubmitting(true)
    try {
      await register(email.trim(), password)
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
        <h1 style={{ fontSize: 20, marginBottom: 4 }}>Create account</h1>
        <p className="subtitle" style={{ marginBottom: 16 }}>
          Your first investigation is created automatically. Documents uploaded before
          sign-up are claimed by the first account.
        </p>

        {error ? <ErrorAlert title="Registration failed" message={error} /> : null}

        <form onSubmit={onSubmit} className="auth-form">
          <label className="field-label" htmlFor="reg-email">
            Email
          </label>
          <input
            id="reg-email"
            className="input"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@example.com"
          />

          <label className="field-label" htmlFor="reg-password">
            Password (min 8 characters)
          </label>
          <input
            id="reg-password"
            className="input"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Choose a password"
          />

          <label className="field-label" htmlFor="reg-confirm">
            Confirm password
          </label>
          <input
            id="reg-confirm"
            className="input"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
            placeholder="Repeat the password"
          />

          <button
            type="submit"
            className="btn btn-primary btn-block"
            disabled={submitting}
            style={{ marginTop: 8 }}
          >
            {submitting ? 'Creating account…' : 'Create account'}
          </button>
        </form>

        <p className="muted small" style={{ marginTop: 14 }}>
          Already registered? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </div>
  )
}
