import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  GitCompareArrows,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  FileStack,
  Link2,
  Play,
  SearchX,
} from 'lucide-react'
import { analysisApi, documentsApi, errorMessage } from '../services/api'
import type { CompareResponse, DocumentRecord } from '../types/api'
import {
  Badge,
  EmptyState,
  ErrorAlert,
  FileIcon,
  LoadingBlock,
} from '../components/primitives'
import { ENTITY_TYPE_LABELS, formatBytes } from '../utils/format'

export function ComparePage() {
  const [documents, setDocuments] = useState<DocumentRecord[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [report, setReport] = useState<CompareResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [listError, setListError] = useState<string | null>(null)
  const [compareError, setCompareError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const loadDocuments = useCallback(() => {
    setLoading(true)
    setListError(null)
    documentsApi
      .list({ page: 1, page_size: 100 })
      .then((response) => {
        setDocuments(response.items)
        setSelected((current) => {
          const valid = new Set([...current].filter((id) => response.items.some((d) => d.id === id)))
          return valid
        })
      })
      .catch((err) => setListError(errorMessage(err)))
      .finally(() => setLoading(false))
  }, [])

  useEffect(loadDocuments, [loadDocuments])

  const toggle = (id: string) => {
    setReport(null)
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const runCompare = async () => {
    setBusy(true)
    setCompareError(null)
    setReport(null)
    try {
      const data = await analysisApi.compare({ document_ids: [...selected] })
      setReport(data)
    } catch (err) {
      setCompareError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  if (loading && documents.length === 0 && !listError) {
    return (
      <div className="card">
        <LoadingBlock label="Loading documents…" />
      </div>
    )
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Cross-document comparison</h1>
          <p className="subtitle">
            Select two or more documents to find shared entities, related records and conflicting
            values. Matching is exact on normalised values plus fuzzy similarity for near-identical
            names — every result names its source documents and pages.
          </p>
        </div>
      </div>

      {listError ? <ErrorAlert message={listError} onRetry={loadDocuments} /> : null}
      {compareError ? (
        <ErrorAlert title="Comparison failed" message={compareError} onRetry={runCompare} />
      ) : null}

      {documents.length === 0 && !listError ? (
        <div className="card">
          <EmptyState
            icon={<FileStack size={24} />}
            title="Nothing to compare yet"
            message="Upload at least two documents, then return here to look for shared and conflicting information."
            action={
              <Link to="/upload" className="btn btn-primary">
                Upload documents
              </Link>
            }
          />
        </div>
      ) : (
        <section className="card">
          <div className="card-head">
            <h3>
              <FileStack size={16} /> Select documents
            </h3>
            <span className="card-hint">
              {selected.size} selected · minimum 2
            </span>
          </div>

          <div className="doc-picker">
            {documents.map((doc) => {
              const isSelected = selected.has(doc.id)
              return (
                <label
                  key={doc.id}
                  className={`doc-option${isSelected ? ' selected' : ''}`}
                >
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => toggle(doc.id)}
                  />
                  <FileIcon extension={doc.file_extension} size={30} />
                  <span className="grow">
                    <span
                      className="file-name"
                      style={{ display: 'block', maxWidth: '100%' }}
                      title={doc.original_filename}
                    >
                      {doc.original_filename}
                    </span>
                    <span className="file-sub">
                      {formatBytes(doc.file_size)} ·{' '}
                      {doc.page_count ? `${doc.page_count} page(s)` : 'image'}
                    </span>
                  </span>
                </label>
              )
            })}
          </div>

          <div className="flex mt-16">
            <button
              type="button"
              className="btn btn-primary"
              disabled={selected.size < 2 || busy}
              onClick={runCompare}
            >
              {busy ? <span className="spinner" /> : <Play size={15} />}
              Compare {selected.size > 0 ? `${selected.size} documents` : ''}
            </button>
            {selected.size > 0 && selected.size < 2 ? (
              <span className="small dim">Select at least one more document.</span>
            ) : null}
          </div>
        </section>
      )}

      {busy ? (
        <div className="card">
          <LoadingBlock label="Analysing documents and comparing extracted values…" />
        </div>
      ) : null}

      {report ? <CompareReport report={report} /> : null}

      {!report && !busy && selected.size >= 2 ? (
        <div className="disclaimer mt-16">
          <AlertTriangle size={15} />
          <span>
            Comparison runs analysis automatically for any selected document that has not been
            analysed yet. Shared values are not inherently suspicious — context matters.
          </span>
        </div>
      ) : null}
    </>
  )
}

function CompareReport({ report }: { report: CompareResponse }) {
  const { summary } = report

  if (summary.shared_entity_count === 0 && summary.conflict_count === 0) {
    return (
      <section className="card mt-16">
        <EmptyState
          icon={<SearchX size={24} />}
          title="No shared values or conflicts found"
          message="The selected documents do not share extracted entities and no conflicting values were detected. This does not prove the documents are unrelated — extraction coverage depends on usable text."
        />
        <div className="disclaimer">
          <span>{report.disclaimer}</span>
        </div>
      </section>
    )
  }

  return (
    <>
      <div className="grid grid-stats mt-16">
        <div className="stat-card">
          <span className="stat-icon accent">
            <GitCompareArrows size={19} />
          </span>
          <div>
            <div className="stat-value">{summary.documents_compared}</div>
            <div className="stat-label">Documents compared</div>
          </div>
        </div>
        <div className="stat-card">
          <span className="stat-icon info">
            <Link2 size={19} />
          </span>
          <div>
            <div className="stat-value">{summary.shared_entity_count}</div>
            <div className="stat-label">Shared values</div>
          </div>
        </div>
        <div className="stat-card">
          <span className="stat-icon success">
            <CheckCircle2 size={19} />
          </span>
          <div>
            <div className="stat-value">{summary.related_record_count}</div>
            <div className="stat-label">Related record pairs</div>
          </div>
        </div>
        <div className="stat-card">
          <span className="stat-icon warning">
            <AlertTriangle size={19} />
          </span>
          <div>
            <div className="stat-value">{summary.conflict_count}</div>
            <div className="stat-label">Conflicts to review</div>
          </div>
        </div>
        {summary.fuzzy_match_count ? (
          <div className="stat-card">
            <span className="stat-icon accent">
              <GitCompareArrows size={19} />
            </span>
            <div>
              <div className="stat-value">{summary.fuzzy_match_count}</div>
              <div className="stat-label">Fuzzy name matches</div>
            </div>
          </div>
        ) : null}
      </div>

      <section className="card">
        <div className="card-head">
          <h3>
            <AlertTriangle size={16} /> Conflicts
          </h3>
          <span className="card-hint">requires human review</span>
        </div>

        {report.conflicts.length === 0 ? (
          <p className="muted">No conflicting values were detected between these documents.</p>
        ) : (
          report.conflicts.map((conflict, index) => (
            <div className="conflict-card" key={`${conflict.conflict_type}-${index}`}>
              <div className="flex flex-wrap" style={{ gap: 8 }}>
                <Badge tone="warning">{conflict.severity}</Badge>
                <Badge tone="neutral">{conflict.conflict_type.replace(/_/g, ' ')}</Badge>
                <span className="finding-title">{conflict.field}</span>
                {conflict.subject ? (
                  <span className="small dim">subject: {conflict.subject}</span>
                ) : null}
              </div>
              <p className="finding-explanation mt-8">{conflict.explanation}</p>
              <div className="conflict-values">
                {conflict.values.map((value, valueIndex) => (
                  <div className="conflict-value" key={`${value.value}-${valueIndex}`}>
                    <strong>{value.value}</strong>
                    <div className="docs">
                      {value.documents
                        .map((doc) => String(doc.document_name ?? doc.document_id))
                        .join(' · ')}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))
        )}
      </section>

      <section className="card">
        <div className="card-head">
          <h3>
            <Link2 size={16} /> Shared entities
          </h3>
          <span className="card-hint">{report.shared_entities.length} values</span>
        </div>

        {report.shared_entities.length === 0 ? (
          <p className="muted">No extracted values appear in more than one document.</p>
        ) : (
          report.shared_entities.map((item, index) => {
            const isFuzzy = item.match_type === 'fuzzy'
            const similarity =
              item.similarity !== null && item.similarity !== undefined ? item.similarity : null
            return (
              <div className="shared-row" key={`${item.entity_type}-${index}`}>
                <div className="grow">
                  <div className="flex flex-wrap" style={{ gap: 8 }}>
                    <Badge tone="accent">
                      {ENTITY_TYPE_LABELS[item.entity_type] ?? item.entity_type}
                    </Badge>
                    <span className="finding-title">{item.value}</span>
                    <Badge tone="neutral">{item.document_count} documents</Badge>
                    {isFuzzy ? (
                      <Badge tone="warning">fuzzy match</Badge>
                    ) : (
                      <Badge tone="neutral">exact match</Badge>
                    )}
                  </div>

                  {isFuzzy && similarity !== null ? (
                    <div className="flex flex-wrap mt-8" style={{ gap: 12, alignItems: 'center' }}>
                      <div className="match-meter" aria-label={`${(similarity * 100).toFixed(1)} percent similar`}>
                        <span className="track">
                          <span
                            className="fill"
                            style={{ width: `${Math.round(similarity * 100)}%` }}
                          />
                        </span>
                        <span className="pct">{(similarity * 100).toFixed(1)}%</span>
                      </div>
                      <span className="small dim">similarity across variants</span>
                    </div>
                  ) : null}

                  {isFuzzy && item.fuzzy_variant ? (
                    <div className="fuzzy-vs">also seen as: “{item.fuzzy_variant}”</div>
                  ) : null}

                  <div className="small dim mt-8">
                    {item.occurrences
                      .map(
                        (occ) =>
                          `${occ.document_name}${occ.page_number ? ` (p.${occ.page_number})` : ''}`,
                      )
                      .join(' · ')}
                  </div>
                </div>
              </div>
            )
          })
        )}
      </section>

      <section className="card">
        <div className="card-head">
          <h3>
            <Link2 size={16} /> Related records
          </h3>
        </div>

        {report.related_records.length === 0 ? (
          <p className="muted">
            No document pair shares two or more distinct values. Pairs sharing at least two values
            are grouped here as potentially related records.
          </p>
        ) : (
          report.related_records.map((record, index) => (
            <div className="shared-row" key={index}>
              <div className="grow">
                <div className="flex flex-wrap" style={{ gap: 8 }}>
                  {record.document_names.map((name) => (
                    <Badge key={name} tone="neutral">
                      {name}
                    </Badge>
                  ))}
                  <ArrowRight size={14} className="dim" />
                  <Badge tone="accent">{record.shared_values.length} shared values</Badge>
                </div>
                <div className="small dim mt-8">
                  {record.shared_values.map((value) => value.value).join(' · ')}
                </div>
              </div>
            </div>
          ))
        )}
      </section>

      <div className="disclaimer mt-16">
        <AlertTriangle size={15} />
        <span>{report.disclaimer}</span>
      </div>
    </>
  )
}
