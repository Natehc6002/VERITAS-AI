import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Download, FileStack, Plus, Trash2 } from 'lucide-react'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { EmptyState, ErrorAlert, SuccessAlert } from '../components/primitives'
import { useAuth } from '../context/AuthContext'
import { documentsApi, errorMessage, investigationsApi } from '../services/api'
import type { InvestigationRecord } from '../types/api'

export function InvestigationsPage() {
  const { investigations, refreshInvestigations } = useAuth()
  const [counts, setCounts] = useState<Record<string, number>>({})
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [created, setCreated] = useState<string | null>(null)
  const [pendingDelete, setPendingDelete] = useState<InvestigationRecord | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [downloadingId, setDownloadingId] = useState<string | null>(null)
  const [pageError, setPageError] = useState<string | null>(null)

  const loadCounts = useCallback(async () => {
    try {
      const listing = await documentsApi.list({ page: 1, page_size: 100 })
      const next: Record<string, number> = {}
      for (const doc of listing.items) {
        if (doc.investigation_id) {
          next[doc.investigation_id] = (next[doc.investigation_id] ?? 0) + 1
        }
      }
      setCounts(next)
    } catch (error) {
      setPageError(errorMessage(error))
    }
  }, [])

  useEffect(() => {
    void loadCounts()
  }, [loadCounts, investigations.length])

  const onCreate = async (event: FormEvent) => {
    event.preventDefault()
    setCreateError(null)
    setCreated(null)
    if (!name.trim()) return
    setCreating(true)
    try {
      const item = await investigationsApi.create(name.trim(), description.trim() || undefined)
      setCreated(item.name)
      setName('')
      setDescription('')
      await refreshInvestigations()
      await loadCounts()
    } catch (error) {
      setCreateError(errorMessage(error))
    } finally {
      setCreating(false)
    }
  }

  const onDelete = async () => {
    if (!pendingDelete) return
    setDeleting(true)
    try {
      await investigationsApi.remove(pendingDelete.id)
      setPendingDelete(null)
      await refreshInvestigations()
      await loadCounts()
    } catch (error) {
      setPageError(errorMessage(error))
      setPendingDelete(null)
    } finally {
      setDeleting(false)
    }
  }

  const onDownload = async (investigation: InvestigationRecord) => {
    setDownloadingId(investigation.id)
    setPageError(null)
    try {
      const blob = await investigationsApi.report(investigation.id)
      const url = URL.createObjectURL(blob)
      const anchor = window.document.createElement('a')
      anchor.href = url
      anchor.download = `veritas-report-${investigation.name.replace(/[^\w-]+/g, '-').slice(0, 32) || 'report'}.pdf`
      window.document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      URL.revokeObjectURL(url)
    } catch (error) {
      setPageError(errorMessage(error))
    } finally {
      setDownloadingId(null)
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Investigations</h1>
          <p className="subtitle">
            Group documents into cases, run analysis and download a complete forensic
            PDF report with evidence and source references.
          </p>
        </div>
      </div>

      {created ? (
        <SuccessAlert title="Investigation created" message={`“${created}” is ready for documents.`} />
      ) : null}
      {pageError ? <ErrorAlert title="Something went wrong" message={pageError} /> : null}
      {createError ? <ErrorAlert title="Could not create investigation" message={createError} /> : null}

      <section className="card">
        <div className="card-head">
          <h3>New investigation</h3>
        </div>
        <form onSubmit={onCreate} className="auth-form">
          <div className="flex" style={{ gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
            <div className="grow" style={{ minWidth: 220 }}>
              <label className="field-label" htmlFor="inv-name">
                Name
              </label>
              <input
                id="inv-name"
                className="input"
                value={name}
                required
                maxLength={200}
                onChange={(event) => setName(event.target.value)}
                placeholder="e.g. Vendor fraud sweep"
              />
            </div>
            <div className="grow" style={{ minWidth: 260 }}>
              <label className="field-label" htmlFor="inv-desc">
                Description (optional)
              </label>
              <input
                id="inv-desc"
                className="input"
                value={description}
                maxLength={2000}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="What is this case about?"
              />
            </div>
            <button type="submit" className="btn btn-primary" disabled={creating}>
              <Plus size={15} /> {creating ? 'Creating…' : 'Create'}
            </button>
          </div>
        </form>
      </section>

      <section className="card">
        <div className="card-head">
          <h3>Your investigations ({investigations.length})</h3>
        </div>
        {investigations.length === 0 ? (
          <EmptyState
            title="No investigations yet"
            message="Create your first investigation above, then upload documents into it."
          />
        ) : (
          <div className="investigation-list">
            {investigations.map((investigation) => (
              <div className="investigation-row" key={investigation.id}>
                <div className="grow">
                  <div className="file-name">{investigation.name}</div>
                  <div className="file-sub">
                    <FileStack size={13} /> {counts[investigation.id] ?? 0} document
                    {(counts[investigation.id] ?? 0) === 1 ? '' : 's'} · created{' '}
                    {new Date(investigation.created_at).toLocaleDateString()}
                  </div>
                  {investigation.description ? (
                    <div className="muted small" style={{ marginTop: 4 }}>
                      {investigation.description}
                    </div>
                  ) : null}
                </div>
                <div className="flex" style={{ gap: 8 }}>
                  <button
                    type="button"
                    className="btn btn-sm btn-primary"
                    onClick={() => void onDownload(investigation)}
                    disabled={downloadingId === investigation.id}
                    title="Download forensic PDF report"
                  >
                    <Download size={14} />
                    {downloadingId === investigation.id ? 'Generating…' : 'Report PDF'}
                  </button>
                  <button
                    type="button"
                    className="btn btn-sm btn-ghost"
                    onClick={() => setPendingDelete(investigation)}
                    aria-label={`Delete ${investigation.name}`}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <ConfirmDialog
        open={pendingDelete !== null}
        title="Delete investigation"
        message={`Delete “${pendingDelete?.name ?? ''}”? Documents stay in your library but leave this investigation.`}
        confirmLabel="Delete"
        danger
        busy={deleting}
        onConfirm={onDelete}
        onCancel={() => !deleting && setPendingDelete(null)}
      />
    </>
  )
}
