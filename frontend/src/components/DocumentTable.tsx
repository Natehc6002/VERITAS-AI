import { Eye, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { DocumentRecord } from '../types/api'
import { FileIcon, StatusBadge } from './primitives'
import { formatBytes, formatDateTime } from '../utils/format'

export function DocumentTable({
  documents,
  onDelete,
}: {
  documents: DocumentRecord[]
  onDelete: (document: DocumentRecord) => void
}) {
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>Document</th>
            <th>Type</th>
            <th>Uploaded</th>
            <th>Size</th>
            <th>Pages</th>
            <th>Status</th>
            <th className="right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {documents.map((doc) => (
            <tr key={doc.id}>
              <td>
                <div className="file-cell">
                  <FileIcon extension={doc.file_extension} />
                  <div style={{ minWidth: 0 }}>
                    <Link to={`/documents/${doc.id}`} className="file-name" title={doc.original_filename}>
                      {doc.original_filename}
                    </Link>
                    <div className="file-sub mono">{doc.sha256_hash.slice(0, 16)}…</div>
                  </div>
                </div>
              </td>
              <td>
                <span className="badge badge-neutral">{doc.file_extension.toUpperCase()}</span>
              </td>
              <td className="muted">{formatDateTime(doc.upload_timestamp)}</td>
              <td className="num muted">{formatBytes(doc.file_size)}</td>
              <td className="num muted">{doc.page_count ?? '—'}</td>
              <td>
                <StatusBadge status={doc.processing_status} />
              </td>
              <td>
                <div className="row-actions">
                  <Link to={`/documents/${doc.id}`} className="btn btn-sm" title="Inspect document">
                    <Eye size={14} />
                    Inspect
                  </Link>
                  <button
                    type="button"
                    className="btn btn-sm btn-danger"
                    title="Delete document"
                    onClick={() => onDelete(doc)}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
