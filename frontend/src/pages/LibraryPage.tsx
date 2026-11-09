import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, ArrowRight, FileStack, Search, Trash2, Upload } from 'lucide-react'
import { documentsApi, errorMessage } from '../services/api'
import type { DocumentRecord } from '../types/api'
import { DocumentTable } from '../components/DocumentTable'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { EmptyState, ErrorAlert, LoadingBlock } from '../components/primitives'
import { pageRangeLabel } from '../utils/format'

type SortKey = 'newest' | 'oldest' | 'name' | 'size'

const SORT_LABELS: Record<SortKey, string> = {
  newest: 'Newest first',
  oldest: 'Oldest first',
  name: 'Filename (A–Z)',
  size: 'Largest first',
}

function sortDocuments(documents: DocumentRecord[], key: SortKey): DocumentRecord[] {
  const copy = [...documents]
  switch (key) {
    case 'oldest':
      return copy.sort((a, b) => a.upload_timestamp.localeCompare(b.upload_timestamp))
    case 'name':
      return copy.sort((a, b) => a.original_filename.localeCompare(b.original_filename))
    case 'size':
      return copy.sort((a, b) => b.file_size - a.file_size)
    case 'newest':
    default:
      return copy.sort((a, b) => b.upload_timestamp.localeCompare(a.upload_timestamp))
  }
}

const PAGE_SIZE = 10

export function LibraryPage() {
  const [documents, setDocuments] = useState<DocumentRecord[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [sort, setSort] = useState<SortKey>('newest')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [pendingDelete, setPendingDelete] = useState<DocumentRecord | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    documentsApi
      .list({ page, page_size: PAGE_SIZE, search: search || undefined })
      .then((response) => {
        setDocuments(response.items)
        setTotal(response.total)
        if (response.items.length === 0 && response.total > 0 && response.page > 1) {
          setPage(1)
        }
      })
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false))
  }, [page, search])

  useEffect(load, [load])

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const sorted = sortDocuments(documents, sort)

  const confirmDelete = async () => {
    if (!pendingDelete) return
    setDeleting(true)
    setDeleteError(null)
    try {
      await documentsApi.remove(pendingDelete.id)
      setPendingDelete(null)
      load()
    } catch (err) {
      setDeleteError(errorMessage(err))
    } finally {
      setDeleting(false)
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Document library</h1>
          <p className="subtitle">
            Search, inspect and manage every stored document. All data shown here comes from the
            backend database.
          </p>
        </div>
        <Link to="/upload" className="btn btn-primary">
          <Upload size={16} /> Upload
        </Link>
      </div>

      <div className="toolbar">
        <form
          className="search-wrap"
          onSubmit={(event) => {
            event.preventDefault()
            setPage(1)
            setSearch(searchInput.trim())
          }}
        >
          <Search size={15} />
          <input
            className="input"
            type="search"
            placeholder="Search by filename…"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            aria-label="Search documents"
          />
        </form>

        <div className="flex">
          <label className="field-label mb-0" htmlFor="sort-select" style={{ marginBottom: 0 }}>
            Sort
          </label>
          <select
            id="sort-select"
            className="select"
            value={sort}
            onChange={(event) => setSort(event.target.value as SortKey)}
          >
            {(Object.keys(SORT_LABELS) as SortKey[]).map((key) => (
              <option key={key} value={key}>
                {SORT_LABELS[key]}
              </option>
            ))}
          </select>
        </div>
      </div>

      {deleteError ? <ErrorAlert title="Delete failed" message={deleteError} onRetry={() => setDeleteError(null)} /> : null}
      {error ? <ErrorAlert message={error} onRetry={load} /> : null}

      {loading && documents.length === 0 && !error ? (
        <div className="card">
          <LoadingBlock label="Loading documents…" />
        </div>
      ) : !loading && documents.length === 0 && !error ? (
        <div className="card">
          <EmptyState
            icon={<FileStack size={24} />}
            title={search ? 'No matching documents' : 'The library is empty'}
            message={
              search
                ? `Nothing matches "${search}". Try a different filename search.`
                : 'Upload PDFs or images to build your investigation library.'
            }
            action={
              search ? (
                <button
                  type="button"
                  className="btn"
                  onClick={() => {
                    setSearchInput('')
                    setSearch('')
                    setPage(1)
                  }}
                >
                  Clear search
                </button>
              ) : (
                <Link to="/upload" className="btn btn-primary">
                  <Upload size={16} /> Upload documents
                </Link>
              )
            }
          />
        </div>
      ) : (
        <>
          <DocumentTable documents={sorted} onDelete={setPendingDelete} />

          <div className="pagination">
            <span className="info">
              {pageRangeLabel(page, PAGE_SIZE, total)} document{total === 1 ? '' : 's'}
              {search ? ` matching "${search}"` : ''}
            </span>
            <div className="controls">
              <button
                type="button"
                className="btn btn-sm"
                disabled={page <= 1}
                onClick={() => setPage((value) => Math.max(1, value - 1))}
              >
                <ArrowLeft size={14} /> Previous
              </button>
              <span className="info">
                Page {page} of {totalPages}
              </span>
              <button
                type="button"
                className="btn btn-sm"
                disabled={page >= totalPages}
                onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
              >
                Next <ArrowRight size={14} />
              </button>
            </div>
          </div>
        </>
      )}

      <ConfirmDialog
        open={pendingDelete !== null}
        title="Delete document"
        message={`Delete "${pendingDelete?.original_filename ?? ''}"? The stored file and all analysis results (text, entities, findings, evidence) will be removed. This cannot be undone.`}
        confirmLabel="Delete"
        danger
        busy={deleting}
        onConfirm={confirmDelete}
        onCancel={() => {
          if (!deleting) setPendingDelete(null)
        }}
      >
        <div className="flex mt-16">
          <Trash2 size={15} className="dim" />
          <span className="small dim">Deletion removes database rows and the file from disk.</span>
        </div>
      </ConfirmDialog>
    </>
  )
}
