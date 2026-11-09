import { useCallback, useState } from 'react'
import { Link } from 'react-router-dom'
import { CheckCircle2, FileWarning, Trash2, XCircle } from 'lucide-react'
import { documentsApi, errorMessage } from '../services/api'
import type { DocumentRecord } from '../types/api'
import { FileDropzone, type PickedFile } from '../components/FileDropzone'
import { ErrorAlert, FileIcon, SuccessAlert } from '../components/primitives'
import { formatBytes } from '../utils/format'

type QueueState =
  | { kind: 'invalid'; file: File; error: string }
  | { kind: 'queued'; file: File }
  | { kind: 'uploading'; file: File; progress: number }
  | { kind: 'done'; file: File; document: DocumentRecord }
  | { kind: 'failed'; file: File; error: string }

export function UploadPage() {
  const [queue, setQueue] = useState<QueueState[]>([])

  const update = useCallback((index: number, next: QueueState) => {
    setQueue((current) => current.map((item, i) => (i === index ? next : item)))
  }, [])

  const uploadOne = useCallback(
    async (index: number, file: File) => {
      update(index, { kind: 'uploading', file, progress: 0 })
      try {
        const document = await documentsApi.upload(file, ({ loaded, total }) => {
          update(index, {
            kind: 'uploading',
            file,
            progress: total > 0 ? Math.round((loaded / total) * 100) : 0,
          })
        })
        update(index, { kind: 'done', file, document })
      } catch (error) {
        update(index, { kind: 'failed', file, error: errorMessage(error) })
      }
    },
    [update],
  )

  const handleFiles = useCallback(
    (picked: PickedFile[]) => {
      const startAt = queue.length
      const next: QueueState[] = picked.map((item) =>
        item.error
          ? { kind: 'invalid', file: item.file, error: item.error }
          : { kind: 'queued', file: item.file },
      )
      setQueue((current) => [...current, ...next])
      next.forEach((item, offset) => {
        if (item.kind === 'queued') {
          void uploadOne(startAt + offset, item.file)
        }
      })
    },
    [queue.length, uploadOne],
  )

  const doneCount = queue.filter((item) => item.kind === 'done').length
  const failedCount = queue.filter((item) => item.kind === 'failed' || item.kind === 'invalid').length
  const uploadingCount = queue.filter((item) => item.kind === 'uploading' || item.kind === 'queued').length

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Upload documents</h1>
          <p className="subtitle">
            Files are validated by extension and content signature, hashed with SHA-256, renamed to
            a server-generated UUID and stored outside the web root.
          </p>
        </div>
      </div>

      {doneCount > 0 && uploadingCount === 0 ? (
        <SuccessAlert
          title={`${doneCount} document${doneCount === 1 ? '' : 's'} uploaded`}
          message="Uploaded documents are stored. Open a document to extract text and run analysis."
        />
      ) : null}

      {failedCount > 0 && uploadingCount === 0 ? (
        <ErrorAlert
          title={`${failedCount} file${failedCount === 1 ? '' : 's'} could not be uploaded`}
          message="See the individual messages below for the reason (type, size or content mismatch)."
        />
      ) : null}

      <section className="card">
        <FileDropzone onFiles={handleFiles} disabled={uploadingCount > 0} />
        {uploadingCount > 0 ? (
          <div className="mt-16 muted small">Uploading {uploadingCount} file(s)…</div>
        ) : null}

        {queue.map((item, index) => (
          <div className="upload-item" key={`${item.file.name}-${index}`}>
            <FileIcon extension={item.file.name.split('.').pop() ?? ''} size={30} />
            <div className="grow">
              <div className="file-name" style={{ maxWidth: '100%' }}>
                {item.file.name}
              </div>
              <div className="file-sub">
                {formatBytes(item.file.size)}
                {item.kind === 'invalid' ? ` · ${item.error}` : null}
                {item.kind === 'failed' ? ` · ${item.error}` : null}
                {item.kind === 'done' ? ' · uploaded' : null}
              </div>
              {item.kind === 'uploading' ? (
                <div className="upload-progress">
                  <div style={{ width: `${item.progress}%` }} />
                </div>
              ) : null}
            </div>

            {item.kind === 'uploading' ? <span className="spinner" /> : null}
            {item.kind === 'done' ? (
              <div className="flex">
                <CheckCircle2 size={17} color="var(--success)" />
                <Link to={`/documents/${item.document.id}`} className="btn btn-sm">
                  Inspect
                </Link>
              </div>
            ) : null}
            {item.kind === 'failed' || item.kind === 'invalid' ? (
              <XCircle size={17} color="var(--danger)" />
            ) : null}
            {item.kind === 'invalid' ? (
              <button
                type="button"
                className="btn btn-sm btn-ghost"
                onClick={() => setQueue((current) => current.filter((_, i) => i !== index))}
                aria-label="Remove from list"
              >
                <Trash2 size={14} />
              </button>
            ) : null}
            {item.kind === 'queued' ? <FileWarning size={16} className="dim" /> : null}
          </div>
        ))}
      </section>

      <section className="card">
        <div className="card-head">
          <h3>Validation rules</h3>
        </div>
        <ul className="muted small" style={{ margin: 0, paddingLeft: 18, lineHeight: 1.9 }}>
          <li>Accepted types: PDF, PNG, JPG, JPEG (checked against the file signature, not the client MIME type).</li>
          <li>Maximum file size: 20 MB. Empty files are rejected.</li>
          <li>Corrupt or password-protected PDFs are rejected with a clear error.</li>
          <li>Identical files are allowed but flagged as duplicates during analysis.</li>
        </ul>
      </section>
    </>
  )
}
