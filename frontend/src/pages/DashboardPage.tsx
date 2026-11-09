import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  FileStack,
  Layers,
  Search,
  Upload,
} from 'lucide-react'
import { analysisApi, errorMessage } from '../services/api'
import type { StatsResponse } from '../types/api'
import { EmptyState, ErrorAlert, FileIcon, LoadingBlock, StatCard, StatusBadge } from '../components/primitives'
import { formatBytes, formatDateTime } from '../utils/format'

export function DashboardPage() {
  const [stats, setStats] = useState<StatsResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    analysisApi
      .stats()
      .then(setStats)
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false))
  }, [])

  useEffect(load, [load])

  if (loading && !stats) return <LoadingBlock label="Loading dashboard statistics…" />
  if (error && !stats) return <ErrorAlert message={error} onRetry={load} />
  if (!stats) return null

  const severity = stats.findings_by_severity ?? {}
  const high = severity.high ?? 0
  const medium = severity.medium ?? 0
  const unprocessed = stats.total_documents - stats.processed_documents

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Investigation dashboard</h1>
          <p className="subtitle">
            Real-time counters from the document store. Indicators shown here are explainable
            observations, not fraud determinations.
          </p>
        </div>
        <Link to="/upload" className="btn btn-primary">
          <Upload size={16} /> Upload documents
        </Link>
      </div>

      {error ? <ErrorAlert message={error} onRetry={load} /> : null}

      <div className="grid grid-stats">
        <StatCard
          icon={<FileStack size={19} />}
          tone="accent"
          value={stats.total_documents}
          label="Total documents"
        />
        <StatCard
          icon={<CheckCircle2 size={19} />}
          tone="success"
          value={stats.processed_documents}
          label="Successfully processed"
        />
        <StatCard
          icon={<AlertTriangle size={19} />}
          tone={unprocessed > 0 ? 'warning' : 'info'}
          value={unprocessed}
          label="Pending / failed processing"
        />
        <StatCard
          icon={<Layers size={19} />}
          tone="info"
          value={stats.documents_with_text}
          label="Documents with extracted text"
        />
        <StatCard
          icon={<Search size={19} />}
          tone={high + medium > 0 ? 'warning' : 'success'}
          value={stats.total_findings}
          label={
            high + medium > 0
              ? `Findings (${high} high · ${medium} medium)`
              : 'Forensic findings recorded'
          }
        />
      </div>

      <div className="grid grid-2 mt-16">
        <section className="card">
          <div className="card-head">
            <h3>
              <Upload size={16} /> Recently uploaded
            </h3>
            <Link to="/documents" className="btn btn-ghost btn-sm">
              View all <ArrowRight size={14} />
            </Link>
          </div>

          {stats.recent_documents.length === 0 ? (
            <EmptyState
              icon={<FileStack size={24} />}
              title="No documents yet"
              message="Upload a PDF or image to start an investigation. Documents are validated, hashed and stored locally."
              action={
                <Link to="/upload" className="btn btn-primary">
                  <Upload size={16} /> Upload your first document
                </Link>
              }
            />
          ) : (
            <div className="table-wrap" style={{ border: 'none' }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>Document</th>
                    <th>Uploaded</th>
                    <th>Size</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.recent_documents.map((doc) => (
                    <tr key={doc.id}>
                      <td>
                        <div className="file-cell">
                          <FileIcon extension={doc.file_extension} size={28} />
                          <Link to={`/documents/${doc.id}`} className="file-name" title={doc.original_filename}>
                            {doc.original_filename}
                          </Link>
                        </div>
                      </td>
                      <td className="muted small">{formatDateTime(doc.upload_timestamp)}</td>
                      <td className="muted num">{formatBytes(doc.file_size)}</td>
                      <td>
                        <StatusBadge status={doc.processing_status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="card">
          <div className="card-head">
            <h3>
              <Layers size={16} /> Intelligence overview
            </h3>
            <Link to="/compare" className="btn btn-ghost btn-sm">
              Compare documents <ArrowRight size={14} />
            </Link>
          </div>

          <div className="kv-grid">
            <div className="kv">
              <div className="k">Entities extracted</div>
              <div className="v" style={{ fontSize: 21, fontWeight: 700 }}>
                {stats.total_entities}
              </div>
            </div>
            <div className="kv">
              <div className="k">High severity</div>
              <div className="v" style={{ fontSize: 21, fontWeight: 700, color: 'var(--danger)' }}>
                {high}
              </div>
            </div>
            <div className="kv">
              <div className="k">Medium severity</div>
              <div className="v" style={{ fontSize: 21, fontWeight: 700, color: 'var(--warning)' }}>
                {medium}
              </div>
            </div>
            <div className="kv">
              <div className="k">Low / info severity</div>
              <div className="v" style={{ fontSize: 21, fontWeight: 700 }}>
                {(severity.low ?? 0) + (severity.info ?? 0)}
              </div>
            </div>
          </div>

          <hr className="divider" />

          <div className="disclaimer">
            <AlertTriangle size={15} />
            <span>
              Every finding links back to the metadata or page text that triggered it. Shared or
              conflicting values across documents require human review — the system never declares
              a document fraudulent on its own.
            </span>
          </div>
        </section>
      </div>
    </>
  )
}
