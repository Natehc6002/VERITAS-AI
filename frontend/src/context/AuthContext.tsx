import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import {
  UNAUTHORIZED_EVENT,
  authApi,
  clearToken,
  getToken,
  investigationsApi,
  setToken,
} from '../services/api'
import type { InvestigationRecord, UserRecord } from '../types/api'

interface AuthState {
  user: UserRecord | null
  investigations: InvestigationRecord[]
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string) => Promise<void>
  logout: () => void
  refreshInvestigations: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserRecord | null>(null)
  const [investigations, setInvestigations] = useState<InvestigationRecord[]>([])
  const [loading, setLoading] = useState<boolean>(() => getToken() !== null)

  const applySession = useCallback(async () => {
    const context = await authApi.me()
    setUser(context.user)
    setInvestigations(context.investigations)
  }, [])

  useEffect(() => {
    let cancelled = false
    if (!getToken()) {
      setUser(null)
      setInvestigations([])
      setLoading(false)
      return
    }
    applySession()
      .catch(() => {
        if (!cancelled) {
          clearToken()
          setUser(null)
          setInvestigations([])
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [applySession])

  useEffect(() => {
    const onUnauthorized = () => {
      setUser(null)
      setInvestigations([])
    }
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
  }, [])

  const login = useCallback(
    async (email: string, password: string) => {
      const token = await authApi.login(email, password)
      setToken(token.access_token)
      await applySession()
    },
    [applySession],
  )

  const register = useCallback(
    async (email: string, password: string) => {
      const token = await authApi.register(email, password)
      setToken(token.access_token)
      await applySession()
    },
    [applySession],
  )

  const logout = useCallback(() => {
    clearToken()
    setUser(null)
    setInvestigations([])
  }, [])

  const refreshInvestigations = useCallback(async () => {
    const items = await investigationsApi.list()
    setInvestigations(items)
  }, [])

  const value = useMemo<AuthState>(
    () => ({ user, investigations, loading, login, register, logout, refreshInvestigations }),
    [user, investigations, loading, login, register, logout, refreshInvestigations],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
