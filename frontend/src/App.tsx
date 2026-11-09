import { Route, Routes } from 'react-router-dom'
import { AppShell } from './layouts/AppShell'
import { DashboardPage } from './pages/DashboardPage'
import { UploadPage } from './pages/UploadPage'
import { LibraryPage } from './pages/LibraryPage'
import { DocumentDetailPage } from './pages/DocumentDetailPage'
import { ComparePage } from './pages/ComparePage'
import { NotFoundPage } from './pages/NotFoundPage'

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/documents" element={<LibraryPage />} />
        <Route path="/documents/:id" element={<DocumentDetailPage />} />
        <Route path="/compare" element={<ComparePage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
