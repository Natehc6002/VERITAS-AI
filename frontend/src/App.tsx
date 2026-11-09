import { type ReactNode } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { AppShell } from './layouts/AppShell'
import { AuthProvider, useAuth } from './context/AuthContext'
import { ToastProvider } from './components/Toast'
import { DashboardPage } from './pages/DashboardPage'
import { UploadPage } from './pages/UploadPage'
import { LibraryPage } from './pages/LibraryPage'
import { DocumentDetailPage } from './pages/DocumentDetailPage'
import { ComparePage } from './pages/ComparePage'
import { InvestigationsPage } from './pages/InvestigationsPage'
import { LoginPage } from './pages/LoginPage'
import { RegisterPage } from './pages/RegisterPage'
import { NotFoundPage } from './pages/NotFoundPage'

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) {
    return (
      <div className="auth-screen">
        <div className="muted">Restoring session…</div>
      </div>
    )
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return <>{children}</>
}

export default function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route
          element={
            <ProtectedRoute>
              <AppShell />
            </ProtectedRoute>
          }
        >
          <Route path="/" element={<DashboardPage />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/documents" element={<LibraryPage />} />
          <Route path="/documents/:id" element={<DocumentDetailPage />} />
          <Route path="/compare" element={<ComparePage />} />
          <Route path="/investigations" element={<InvestigationsPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
        </Routes>
      </ToastProvider>
    </AuthProvider>
  )
}
