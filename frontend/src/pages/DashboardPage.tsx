import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  FileStack,
  FolderOpen,
  GitCompareArrows,
  Layers,
  Search,
  Upload,
} from 'lucide-react'
import { analysisApi, documentsApi, errorMessage, investigationsApi } from '../services/api'
import type { InvestigationRecord, StatsResponse } from '../types/api'
import { EmptyState, ErrorAlert, FileIcon, StatCard, StatusBadge } from '../components/primitives'
import { useAuth } from '../context/AuthContext'
import { formatBytes, formatDate, formatDateTime } from '../utils/format'

function greeting(): string {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

function displayName(email: string): string {
  const part = email.split('@')[0] || ''
  const words = part.split(/[._-]+/).filter(Boolean)
  if (words.length === 0) return part
  return words
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

function DashboardSkeleton() {
  return (
    <>
      <div className="skeleton" style={{ height: 118, borderRadius: 10, marginBottom: 20 }} />
      <div className="grid grid-stats" style={{ marginBottom: 16 }}>
        {[0, 1, 2, 3, 4].map((index) => (
          <div className="skeleton-stat" key={index}>
            <span className="skeleton sk-icon" />
            <div className="sk-lines">
              <span className="skeleton" />
              <span className="skeleton" />
            </div>
          </div>
        ))}
      </div>
      <div className="grid grid-2">
        <div className="card">
          <div className="skeleton skeleton-line" style={{ width: '40%', marginBottom: 16 }} />
          {[0, 1, 2].map((index) => (
            <div className="skeleton-row" key={index}>
              <span className="skeleton" />
              <span className="skeleton" />
              <span className="skeleton" />
            </div>
          ))}
        </div>
        <div className="card">
          <div className="skeleton skeleton-line" style={{ width: '50%', marginBottom: 16 }} />
          <div className="skeleton" style={{ height: 90 }} />
        </div>
      </div>
    </>
  )
}

export function DashboardPage() {
  const { user } = useAuth()
  const [stats, setStats] = useState<StatsResponse | null>(null)
  const [investigations, setInvestigations] = useState<InvestigationRecord[]>([])
  const [docCounts, setDocCounts] = useState<Record<string, number>>({})
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    Promise.all([
      analysisApi.stats(),
      investigationsApi.list(),
      documentsApi.list({ page: 1, page_size: 100 }),
    ])
      .then(([statsData, invData, docData]) => {
        setStats(statsData)
        setInvestigations(invData)
        const counts: Record<string, number> = {}
        for (const doc of docData.items) {
          if (doc.investigation_id) {
            counts[doc.investigation_id] = (counts[doc.investigation_id] ?? 0) + 1
          }
        }
        setDocCounts(counts)
      })
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false))
  }, [])

  useEffect(load, [load])

  if (loading && !stats) return <DashboardSkeleton />
  if (error && !stats) return <ErrorAlert message={error} onRetry={load} />
  if (!stats) return null

  const severity = stats.findings_by_severity ?? {}
  const high = severity.high ?? 0
  const medium = severity.medium ?? 0
  const low = severity.low ?? 0
  const info = severity.info ?? 0
  const totalSeverity = high + medium + low + info
  const unprocessed = stats.total_documents - stats.processed_documents
  const today = new Date().toLocaleDateString(undefined, {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })

  const severityPct = (value: number) => (totalSeverity > 0 ? (value / totalSeverity) * 100 : 0)

  return (
    <>
      <section className="hero">
        <div>
          <div className="kicker">{today}</div>
          <h1>
            {greeting()}
            {user ? `, ${displayName(user.email)}` : ''}
          </h1>
          <p className="subtitle">
            Evidence store, forensic indicators and cross-document correlation — every signal is
            an explainable observation with traceable source data, never an automated verdict.
          </p>
        </div>
        <div className="hero-actions">
          <Link to="/upload" className="btn btn-primary">
            <Upload size={16} /> Upload documents
          </Link>
          <Link to="/compare" className="btn">
            <GitCompareArrows size={16} /> Run comparison
          </Link>
        </div>
      </section>

      <div className="quick-grid">
        <Link to="/upload" className="quick-action">
          <span className="qa-icon">
            <Upload size={17} />
          </span>
          <span>
            <span className="qa-title">Ingest evidence</span>
            <span className="qa-sub">PDF or image · signature-validated · SHA-256 hashed</span>
          </span>
        </Link>
        <Link to="/documents" className="quick-action">
          <span className="qa-icon">
            <FileStack size={17} />
          </span>
          <span>
            <span className="qa-title">Evidence library</span>
            <span className="qa-sub">
              {stats.total_documents} document{stats.total_documents === 1 ? '' : 's'} stored
            </span>
          </span>
        </Link>
        <Link to="/compare" className="quick-action">
          <span className="qa-icon">
            <GitCompareArrows size={17} />
          </span>
          <span>
            <span className="qa-title">Compare documents</span>
            <span className="qa-sub">Exact + fuzzy entity correlation across cases</span>
          </span>
        </Link>
        <Link to="/investigations" className="quick-action">
          <span className="qa-icon">
            <FolderOpen size={17} />
          </span>
          <span>
            <span className="qa-title">Case files</span>
            <span className="qa-sub">
              {investigations.length} investigation{investigations.length === 1 ? '' : 's'} ·
              PDF reports
            </span>
          </span>
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
              <Upload size={16} /> Recent documents
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
              <FolderOpen size={16} /> Recent investigations
            </h3>
            <Link to="/investigations" className="btn btn-ghost btn-sm">
              Manage <ArrowRight size={14} />
            </Link>
          </div>

          {investigations.length === 0 ? (
            <EmptyState
              icon={<FolderOpen size={24} />}
              title="No case files yet"
              message="Group documents into an investigation to generate a forensic PDF report with evidence and source references."
              action={
                <Link to="/investigations" className="btn btn-primary">
                  <FolderOpen size={16} /> Create an investigation
                </Link>
              }
            />
          ) : (
            <div className="investigation-list">
              {investigations.slice(0, 5).map((investigation) => (
                <div className="case-row" key={investigation.id}>
                  <span className="case-icon">
                    <FolderOpen size={17} />
                  </span>
                  <div className="grow">
                    <div className="file-name" style={{ maxWidth: '100%' }}>
                      {investigation.name}
                    </div>
                    <div className="case-meta">
                      <span>
                        {docCounts[investigation.id] ?? 0} document
                        {(docCounts[investigation.id] ?? 0) === 1 ? '' : 's'}
                      </span>
                      <span>·</span>
                      <span>opened {formatDate(investigation.created_at)}</span>
                    </div>
                  </div>
                  <Link to="/investigations" className="btn btn-sm">
                    Open
                  </Link>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      <div className="grid grid-2 mt-16">
        <section className="card">
          <div className="card-head">
            <h3>
              <AlertTriangle size={16} /> Findings by severity
            </h3>
            <span className="card-hint">{stats.total_findings} total</span>
          </div>

          {totalSeverity === 0 ? (
            <p className="muted">
              No forensic indicators recorded yet. Findings appear once documents are analysed.
            </p>
          ) : (
            <>
              <div
                className="meter"
                role="img"
                aria-label={`Severity distribution: ${high} high, ${medium} medium, ${low} low, ${info} info`}
              >
                <span className="seg-high" style={{ width: `${severityPct(high)}%` }} />
                <span className="seg-medium" style={{ width: `${severityPct(medium)}%` }} />
                <span className="seg-low" style={{ width: `${severityPct(low)}%` }} />
                <span className="seg-info" style={{ width: `${severityPct(info)}%` }} />
              </div>
              <div className="meter-legend">
                <span className="item">
                  <span className="swatch" style={{ background: 'var(--danger)' }} /> {high} high
                </span>
                <span className="item">
                  <span className="swatch" style={{ background: 'var(--warning)' }} /> {medium} medium
                </span>
                <span className="item">
                  <span className="swatch" style={{ background: 'var(--info)' }} /> {low} low
                </span>
                <span className="item">
                  <span className="swatch" style={{ background: '#64748f' }} /> {info} info
                </span>
              </div>
            </>
          )}

          <hr className="divider" />

          <div className="kv-grid">
            <div className="kv">
              <div className="k">Entities extracted</div>
              <div className="v" style={{ fontSize: 21, fontWeight: 700 }}>
                {stats.total_entities}
              </div>
            </div>
            <div className="kv">
              <div className="k">Documents with text</div>
              <div className="v" style={{ fontSize: 21, fontWeight: 700 }}>
                {stats.documents_with_text}
              </div>
            </div>
          </div>

          <div className="disclaimer mt-16">
            <AlertTriangle size={15} />
            <span>
              Every finding links back to the metadata or page text that triggered it. Shared or
              conflicting values across documents require human review — the system never declares
              a document fraudulent on its own.
            </span>
          </div>
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
                {low + info}
              </div>
            </div>
            <div className="kv">
              <div className="k">Investigations</div>
              <div className="v" style={{ fontSize: 21, fontWeight: 700 }}>
                {investigations.length}
              </div>
            </div>
          </div>

          <hr className="divider" />

          <div className="section-kicker">Processing coverage</div>
          <div className="meter" role="img" aria-label={`${stats.processed_documents} of ${stats.total_documents} processed`}>
            <span
              className="seg-info"
              style={{
                width: `${stats.total_documents > 0 ? (stats.processed_documents / stats.total_documents) * 100 : 0}%`,
                background: 'var(--success)',
              }}
            />
          </div>
          <div className="meter-legend">
            <span className="item">
              <span className="swatch" style={{ background: 'var(--success)' }} />{' '}
              {stats.processed_documents} processed
            </span>
            <span className="item">
              <span className="swatch" style={{ background: 'var(--panel-3)' }} /> {unprocessed} pending
            </span>
          </div>

          <div className="disclaimer mt-16">
            <AlertTriangle size={15} />
            <span>
              Coverage is calculated from stored document status only. OCR confidence and entity
              values are reported as extracted — never fabricated.
            </span>
          </div>
        </section>
      </div>
    </>
  )
}
