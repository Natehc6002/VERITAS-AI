import { Link } from 'react-router-dom'
import { SearchX } from 'lucide-react'

export function NotFoundPage() {
  return (
    <div className="not-found">
      <div className="code">404</div>
      <h1>Page not found</h1>
      <p className="muted mt-8">The page you requested does not exist.</p>
      <div className="mt-16">
        <Link to="/" className="btn btn-primary">
          Back to dashboard
        </Link>
      </div>
      <div className="dim mt-16" style={{ display: 'inline-flex', gap: 8, alignItems: 'center' }}>
        <SearchX size={15} /> Check the URL or use the sidebar.
      </div>
    </div>
  )
}
