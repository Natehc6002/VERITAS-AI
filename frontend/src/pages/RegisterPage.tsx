import { useMemo, useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { Check, Eye, EyeOff, Loader2, Lock, Mail, ShieldCheck } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { errorMessage } from '../services/api'
import { ErrorAlert } from '../components/primitives'
import { AuthAside } from '../components/AuthAside'

export function RegisterPage() {
  const { user, loading, register } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (!loading && user) {
    return <Navigate to="/" replace />
  }

  const emailValid = /.+@.+\..+/.test(email.trim())
  const lengthOk = password.length >= 8
  const matchOk = confirm.length > 0 && password === confirm
  const matchFail = confirm.length > 0 && password !== confirm
  const canSubmit = emailValid && lengthOk && password === confirm && !submitting

  const rules = useMemo(
    () => [
      { label: 'At least 8 characters', ok: lengthOk },
      { label: 'Email format valid', ok: emailValid },
      { label: 'Passwords match', ok: matchOk },
    ],
    [lengthOk, emailValid, matchOk],
  )

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
    <div className="auth-screen auth-layout">
      <AuthAside mode="register" />

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
          <h1 style={{ fontSize: 20, marginBottom: 4 }}>Create account</h1>
          <p className="subtitle" style={{ marginBottom: 16 }}>
            Your first investigation is created automatically. Documents uploaded before
            sign-up are claimed by the first account.
          </p>

          {error ? <ErrorAlert title="Registration failed" message={error} /> : null}

          <form onSubmit={onSubmit} className="auth-form">
            <label className="field-label" htmlFor="reg-email">
              <Mail size={13} /> Email
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
              aria-invalid={email.length > 0 && !emailValid}
            />
            {email.length > 0 && !emailValid ? (
              <div className="field-hint bad">Enter a valid email address.</div>
            ) : null}

            <label className="field-label" htmlFor="reg-password">
              <Lock size={13} /> Password
            </label>
            <span className="input-wrap">
              <input
                id="reg-password"
                className="input"
                type={showPassword ? 'text' : 'password'}
                autoComplete="new-password"
                required
                minLength={8}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Choose a password"
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
            {password.length > 0 && !lengthOk ? (
              <div className="field-hint bad">Passwords are at least 8 characters.</div>
            ) : (
              <div className="field-hint">Minimum 8 characters.</div>
            )}

            <label className="field-label" htmlFor="reg-confirm">
              Confirm password
            </label>
            <span className="input-wrap">
              <input
                id="reg-confirm"
                className="input"
                type={showPassword ? 'text' : 'password'}
                autoComplete="new-password"
                required
                minLength={8}
                value={confirm}
                onChange={(event) => setConfirm(event.target.value)}
                placeholder="Repeat the password"
                aria-invalid={matchFail}
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
            {matchFail ? (
              <div className="field-hint bad">Passwords do not match.</div>
            ) : matchOk ? (
              <div className="field-hint ok">
                <Check size={11} style={{ verticalAlign: -1 }} /> Passwords match.
              </div>
            ) : null}

            <ul
              className="meter-legend"
              style={{ listStyle: 'none', padding: 0, margin: '10px 0 0' }}
              aria-label="Password requirements"
            >
              {rules.map((rule) => (
                <li
                  key={rule.label}
                  className="item"
                  style={{ color: rule.ok ? 'var(--success)' : undefined }}
                >
                  <span
                    className="swatch"
                    style={{
                      background: rule.ok ? 'var(--success)' : 'var(--panel-3)',
                      borderRadius: '50%',
                    }}
                  />
                  {rule.label}
                </li>
              ))}
            </ul>

            <button
              type="submit"
              className="btn btn-primary btn-block"
              disabled={!canSubmit}
              style={{ marginTop: 12 }}
            >
              {submitting ? (
                <>
                  <Loader2 size={16} className="spin" /> Creating account…
                </>
              ) : (
                'Create account'
              )}
            </button>
          </form>

          <p className="muted small" style={{ marginTop: 14 }}>
            Already registered? <Link to="/login">Sign in</Link>
          </p>
        </div>
      </div>
    </div>
  )
}
