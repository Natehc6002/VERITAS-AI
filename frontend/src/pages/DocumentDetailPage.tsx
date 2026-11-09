import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  ArrowLeft,
  BrainCircuit,
  Database,
  FileSearch,
  ScrollText,
  Sparkles,
  Trash2,
  Zap,
} from 'lucide-react'
import { analysisApi, documentsApi, errorMessage } from '../services/api'
import type { AnalysisBundle, DocumentRecord, ExtractionResponse } from '../types/api'
import { ConfirmDialog } from '../components/ConfirmDialog'
import {
  Badge,
  Collapsible,
  EmptyState,
  ErrorAlert,
  FileIcon,
  InfoAlert,
  LoadingBlock,
  SeverityBadge,
  StatusBadge,
  WarningAlert,
} from '../components/primitives'
import {
  CATEGORY_LABELS,
  ENTITY_TYPE_LABELS,
  FINDING_CATEGORY_LABELS,
  formatBytes,
  formatDateTime,
} from '../utils/format'

type TabKey = 'overview' | 'text' | 'analysis' | 'evidence'

export function DocumentDetailPage() {
  const { id = '' } = useParams()
  const navigate = useNavigate()

  const [document, setDocument] = useState<DocumentRecord | null>(null)
  const [extraction, setExtraction] = useState<ExtractionResponse | null>(null)
  const [analysis, setAnalysis] = useState<AnalysisBundle | null>(null)
  const [tab, setTab] = useState<TabKey>('overview')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<'extract' | 'analyze' | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [openFindings, setOpenFindings] = useState<Set<string>>(new Set())

  const loadDocument = useCallback(() => {
    setLoading(true)
    setError(null)
    documentsApi
      .get(id)
      .then(setDocument)
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false))
  }, [id])

  useEffect(loadDocument, [loadDocument])

  // Best-effort hydration of existing analysis artifacts (404 simply means "not run yet").
  useEffect(() => {
    let cancelled = false
    analysisApi
      .getText(id)
      .then((data) => !cancelled && setExtraction(data))
      .catch(() => undefined)
    analysisApi
      .getAnalysis(id)
      .then((data) => !cancelled && setAnalysis(data))
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [id])

  const runExtract = async () => {
    setBusy('extract')
    setActionError(null)
    try {
      const data = await analysisApi.extract(id)
      setExtraction(data)
    } catch (err) {
      setActionError(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  const runAnalyze = async () => {
    setBusy('analyze')
    setActionError(null)
    try {
      const data = await analysisApi.analyze(id)
      setAnalysis(data)
      setExtraction(data.extraction)
      setTab('analysis')
    } catch (err) {
      setActionError(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  const removeDocument = async () => {
    setDeleting(true)
    try {
      await documentsApi.remove(id)
      navigate('/documents')
    } catch (err) {
      setActionError(errorMessage(err))
      setDeleting(false)
      setConfirmDelete(false)
    }
  }

  if (loading && !document) return <LoadingBlock label="Loading document…" />
  if (error && !document) {
    return (
      <>
        <ErrorAlert message={error} onRetry={loadDocument} />
        <Link to="/documents" className="btn">
          <ArrowLeft size={15} /> Back to library
        </Link>
      </>
    )
  }
  if (!document) return null

  const isImage = ['png', 'jpg', 'jpeg'].includes(document.file_extension.toLowerCase())
  const pdfMeta = document.pdf_metadata?.metadata ?? {}

  return (
    <>
      <div className="detail-header">
        <div className="detail-title">
          <FileIcon extension={document.file_extension} size={44} />
          <div style={{ minWidth: 0 }}>
            <div className="flex flex-wrap" style={{ gap: 8 }}>
              <Badge tone="neutral">{document.file_extension.toUpperCase()}</Badge>
              <StatusBadge status={document.processing_status} />
            </div>
            <h1 className="mt-8" style={{ marginTop: 6 }}>
              {document.original_filename}
            </h1>
            <div className="dim small">
              {formatBytes(document.file_size)} · uploaded {formatDateTime(document.upload_timestamp)}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap">
          <Link to="/documents" className="btn">
            <ArrowLeft size={15} /> Library
          </Link>
          <button
            type="button"
            className="btn btn-primary"
            onClick={runAnalyze}
            disabled={busy !== null}
            title="Run extraction, classification, entities and indicators"
          >
            {busy === 'analyze' ? <span className="spinner" /> : <Sparkles size={16} />}
            Run analysis
          </button>
          <button
            type="button"
            className="btn btn-danger"
            onClick={() => setConfirmDelete(true)}
            disabled={deleting}
          >
            <Trash2 size={15} /> Delete
          </button>
        </div>
      </div>

      {actionError ? <ErrorAlert title="Operation failed" message={actionError} onRetry={() => setActionError(null)} /> : null}

      <div className="tabs" role="tablist">
        {(
          [
            ['overview', 'Overview', <Database key="i" size={15} />],
            ['text', 'Extracted text', <ScrollText key="i" size={15} />],
            ['analysis', 'Analysis', <BrainCircuit key="i" size={15} />],
            ['evidence', 'Evidence', <FileSearch key="i" size={15} />],
          ] as Array<[TabKey, string, React.ReactNode]>
        ).map(([key, label, icon]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            className={`tab${tab === key ? ' active' : ''}`}
            onClick={() => setTab(key)}
          >
            {icon}
            {label}
            {key === 'analysis' && analysis ? (
              <span className="count">{analysis.findings.length}</span>
            ) : null}
            {key === 'evidence' && analysis ? (
              <span className="count">
                {analysis.findings.reduce((sum, finding) => sum + finding.evidence.length, 0)}
              </span>
            ) : null}
          </button>
        ))}
      </div>

      {tab === 'overview' ? (
        <OverviewTab document={document} pdfMeta={pdfMeta} analysis={analysis} isImage={isImage} />
      ) : null}

      {tab === 'text' ? (
        <TextTab
          extraction={extraction}
          busy={busy === 'extract'}
          onExtract={runExtract}
        />
      ) : null}

      {tab === 'analysis' ? (
        <AnalysisTab analysis={analysis} busy={busy === 'analyze'} onAnalyze={runAnalyze}
          openFindings={openFindings}
          toggleFinding={(findingId) =>
            setOpenFindings((current) => {
              const next = new Set(current)
              if (next.has(findingId)) next.delete(findingId)
              else next.add(findingId)
              return next
            })
          }
        />
      ) : null}

      {tab === 'evidence' ? <EvidenceTab analysis={analysis} /> : null}

      <ConfirmDialog
        open={confirmDelete}
        title="Delete document"
        message={`Delete "${document.original_filename}" and all of its stored analysis? This removes the file from disk and cannot be undone.`}
        confirmLabel="Delete permanently"
        danger
        busy={deleting}
        onConfirm={removeDocument}
        onCancel={() => !deleting && setConfirmDelete(false)}
      />
    </>
  )
}

function OverviewTab({
  document,
  pdfMeta,
  analysis,
  isImage,
}: {
  document: DocumentRecord
  pdfMeta: Record<string, string>
  analysis: AnalysisBundle | null
  isImage: boolean
}) {
  return (
    <>
      <section className="card">
        <div className="card-head">
          <h3>
            <Database size={16} /> File record
          </h3>
        </div>
        <div className="kv-grid">
          <div className="kv">
            <div className="k">Original filename</div>
            <div className="v">{document.original_filename}</div>
          </div>
          <div className="kv">
            <div className="k">MIME type</div>
            <div className="v mono">{document.mime_type}</div>
          </div>
          <div className="kv">
            <div className="k">File size</div>
            <div className="v">{formatBytes(document.file_size)}</div>
          </div>
          <div className="kv">
            <div className="k">Uploaded</div>
            <div className="v">{formatDateTime(document.upload_timestamp)}</div>
          </div>
          <div className="kv">
            <div className="k">Page count</div>
            <div className="v">{document.page_count ?? (isImage ? 'Image (single surface)' : '—')}</div>
          </div>
          <div className="kv">
            <div className="k">Processing status</div>
            <div className="v">
              <StatusBadge status={document.processing_status} />
            </div>
          </div>
          <div className="kv" style={{ gridColumn: '1 / -1' }}>
            <div className="k">SHA-256 hash</div>
            <div className="v mono" title={document.sha256_hash}>
              {document.sha256_hash}
            </div>
          </div>
        </div>
      </section>

      <section className="card">
        <div className="card-head">
          <h3>
            <FileSearch size={16} /> {isImage ? 'Image metadata' : 'PDF metadata'}
          </h3>
          <span className="card-hint">Extracted server-side with PyMuPDF</span>
        </div>

        {isImage && Object.keys(pdfMeta).length === 0 ? (
          <p className="muted small">
            Image files are stored and validated; format-level details (dimensions, colour mode) are
            not extracted in this milestone.
          </p>
        ) : Object.keys(pdfMeta).length === 0 ? (
          <p className="muted small">
            No PDF information dictionary fields were populated. This is common for programmatically
            generated files and is not by itself suspicious.
          </p>
        ) : (
          <div className="kv-grid">
            {Object.entries(pdfMeta).map(([key, value]) => (
              <div className="kv" key={key}>
                <div className="k">{key}</div>
                <div className="v mono">{value}</div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="card">
        <div className="card-head">
          <h3>
            <Sparkles size={16} /> Factual summary
          </h3>
        </div>
        {analysis?.summary ? (
          <>
            <p className="muted" style={{ lineHeight: 1.7 }}>
              {analysis.summary}
            </p>
            <div className="disclaimer mt-16">
              <span>Generated deterministically from extracted metadata and text — no invented content.</span>
            </div>
          </>
        ) : (
          <EmptyState
            icon={<BrainCircuit size={24} />}
            title="Analysis has not run yet"
            message="Run the analysis to classify the document, extract entities, generate a factual summary and raise explainable indicators."
            action={
              <span className="muted small">Use the “Run analysis” button above.</span>
            }
          />
        )}
      </section>
    </>
  )
}

function TextTab({
  extraction,
  busy,
  onExtract,
}: {
  extraction: ExtractionResponse | null
  busy: boolean
  onExtract: () => void
}) {
  return (
    <section className="card">
      <div className="card-head">
        <h3>
          <ScrollText size={16} /> Extracted text
        </h3>
        <div className="flex">
          {extraction ? (
            <span className="small dim">
              {extraction.method === 'native'
                ? 'Native PDF extraction'
                : extraction.method === 'ocr'
                  ? 'OCR-derived text'
                  : 'No extraction method used'}{' '}
              · {extraction.word_count} words
            </span>
          ) : null}
          <button type="button" className="btn btn-sm" onClick={onExtract} disabled={busy}>
            {busy ? <span className="spinner" /> : <Zap size={14} />}
            {extraction ? 'Re-extract' : 'Extract text'}
          </button>
        </div>
      </div>

      {!extraction && !busy ? (
        <EmptyState
          icon={<ScrollText size={24} />}
          title="No text has been extracted"
          message="Extract the document to read its text page by page. PDFs use native extraction; scanned files fall back to OCR when available."
        />
      ) : null}

      {busy && !extraction ? <LoadingBlock label="Extracting text…" /> : null}

      {extraction ? (
        <>
          {extraction.status === 'no_text' ? (
            <WarningAlert
              title="No usable text layer"
              message={extraction.error ?? 'The document contains no extractable text.'}
            />
          ) : null}
          {extraction.status === 'failed' ? (
            <ErrorAlert title="Extraction failed" message={extraction.error ?? 'Unknown error.'} />
          ) : null}
          {extraction.status === 'completed' && extraction.method === 'ocr' ? (
            <InfoAlert
              title="Text derived from OCR"
              message={`OCR confidence values are reported per page when the engine provides them. Pages: ${extraction.page_count ?? extraction.pages.length}.`}
            />
          ) : null}

          <div className="kv-grid mb-0" style={{ marginBottom: 16 }}>
            <div className="kv">
              <div className="k">Status</div>
              <div className="v">
                <StatusBadge status={extraction.status} />
              </div>
            </div>
            <div className="kv">
              <div className="k">Method</div>
              <div className="v">{extraction.method}</div>
            </div>
            <div className="kv">
              <div className="k">Characters</div>
              <div className="v">{extraction.char_count.toLocaleString()}</div>
            </div>
            <div className="kv">
              <div className="k">Words</div>
              <div className="v">{extraction.word_count.toLocaleString()}</div>
            </div>
            <div className="kv">
              <div className="k">OCR engine available</div>
              <div className="v">{extraction.ocr_available ? 'Yes' : 'No'}</div>
            </div>
            <div className="kv">
              <div className="k">Pages</div>
              <div className="v">{extraction.pages.length}</div>
            </div>
          </div>

          {extraction.pages.map((page) => (
            <div className="page-block" key={page.page_number}>
              <div className="page-block-head">
                <span>Page {page.page_number}</span>
                <Badge tone="neutral">{page.method}</Badge>
                <span>
                  {page.word_count} words · {page.char_count} chars
                </span>
                {page.confidence !== null ? (
                  <Badge tone="accent">OCR confidence {(page.confidence * 100).toFixed(1)}%</Badge>
                ) : null}
              </div>
              <div className="text-viewer">
                {page.text.trim() ? page.text : '(no text recognised on this page)'}
              </div>
            </div>
          ))}
        </>
      ) : null}
    </section>
  )
}

function AnalysisTab({
  analysis,
  busy,
  onAnalyze,
  openFindings,
  toggleFinding,
}: {
  analysis: AnalysisBundle | null
  busy: boolean
  onAnalyze: () => void
  openFindings: Set<string>
  toggleFinding: (id: string) => void
}) {
  if (!analysis) {
    return (
      <section className="card">
        <EmptyState
          icon={<BrainCircuit size={24} />}
          title="No analysis results"
          message="Run the analysis to classify this document, extract entities and raise explainable forensic indicators with evidence."
          action={
            <button type="button" className="btn btn-primary" onClick={onAnalyze} disabled={busy}>
              {busy ? <span className="spinner" /> : <Sparkles size={16} />}
              Run analysis
            </button>
          }
        />
      </section>
    )
  }

  const classification = analysis.classification

  return (
    <>
      <section className="card">
        <div className="card-head">
          <h3>
            <BrainCircuit size={16} /> Classification
          </h3>
          <span className="card-hint">
            {classification.method === 'rule_based_baseline'
              ? 'Explainable keyword/pattern baseline (not a learned model)'
              : classification.method ?? ''}
          </span>
        </div>

        <div className="kv-grid">
          <div className="kv">
            <div className="k">Category</div>
            <div className="v" style={{ fontWeight: 650, fontSize: 16 }}>
              {classification.category
                ? (CATEGORY_LABELS[classification.category] ?? classification.category)
                : 'Unclassified'}
            </div>
          </div>
          <div className="kv">
            <div className="k">Confidence</div>
            <div className="v">
              {classification.confidence !== null && classification.confidence !== undefined
                ? `${(classification.confidence * 100).toFixed(0)}%`
                : '—'}
            </div>
          </div>
          <div className="kv">
            <div className="k">Status</div>
            <div className="v">
              <StatusBadge status={classification.status} />
            </div>
          </div>
        </div>

        {classification.rationale && classification.rationale.length > 0 ? (
          <>
            <div className="field-label mt-16">Rules that fired</div>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Rule</th>
                    <th>Category</th>
                    <th>Matched text</th>
                    <th>Weight</th>
                  </tr>
                </thead>
                <tbody>
                  {classification.rationale.map((item, index) => (
                    <tr key={`${item.rule}-${index}`}>
                      <td>{item.rule}</td>
                      <td>
                        <Badge tone="neutral">{item.category}</Badge>
                      </td>
                      <td className="mono">{item.matched}</td>
                      <td className="num">{item.weight}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <p className="muted small mt-16">No category rules matched — the document is labelled “Other”.</p>
        )}
      </section>

      <section className="card">
        <div className="card-head">
          <h3>
            <Zap size={16} /> Extracted entities
          </h3>
          <span className="card-hint">{analysis.entities.length} found</span>
        </div>

        {analysis.entities.length === 0 ? (
          <EmptyState
            icon={<Zap size={24} />}
            title="No entities extracted"
            message="Entity extraction needs usable text. Extract text first (OCR for scanned files) and re-run the analysis."
          />
        ) : (
          <div className="entity-grid">
            {analysis.entities.map((entity) => (
              <div className="entity-chip" key={entity.id}>
                <div className="grow">
                  <div className="entity-type">
                    {ENTITY_TYPE_LABELS[entity.entity_type] ?? entity.entity_type}
                    {entity.page_number ? ` · p.${entity.page_number}` : ''}
                  </div>
                  <div className="entity-value">{entity.value}</div>
                  {entity.source_text ? (
                    <div className="entity-source" title={entity.source_text}>
                      “{entity.source_text}”
                    </div>
                  ) : null}
                </div>
                {entity.confidence !== null ? (
                  <Badge tone="neutral">{(entity.confidence * 100).toFixed(0)}%</Badge>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="card">
        <div className="card-head">
          <h3>
            <FileSearch size={16} /> Forensic indicators
          </h3>
          <span className="card-hint">{analysis.findings.length} raised</span>
        </div>

        <div className="disclaimer" style={{ marginBottom: 14 }}>
          <span>{analysis.disclaimer}</span>
        </div>

        {analysis.findings.length === 0 ? (
          <EmptyState
            icon={<FileSearch size={24} />}
            title="No indicators raised"
            message="The rule set did not detect any anomalies worth reporting for this document."
          />
        ) : (
          analysis.findings.map((finding) => (
            <Collapsible
              key={finding.id}
              open={openFindings.has(finding.id)}
              onToggle={() => toggleFinding(finding.id)}
              title={
                <div className="flex flex-wrap" style={{ gap: 10 }}>
                  <span className="finding-title">{finding.title}</span>
                </div>
              }
            >
              <div className="flex flex-wrap" style={{ gap: 8, marginBottom: 10 }}>
                <SeverityBadge severity={finding.severity} />
                <Badge tone="neutral">
                  {FINDING_CATEGORY_LABELS[finding.category] ?? finding.category}
                </Badge>
                <Badge tone="neutral">{finding.detection_method}</Badge>
                {finding.page_number ? <Badge tone="accent">page {finding.page_number}</Badge> : null}
                {finding.confidence !== null ? (
                  <Badge tone="neutral">confidence {(finding.confidence * 100).toFixed(0)}%</Badge>
                ) : null}
              </div>

              <p className="finding-explanation">{finding.explanation}</p>

              {finding.evidence.length > 0 ? (
                <>
                  <div className="field-label mt-16">Supporting evidence ({finding.evidence.length})</div>
                  {finding.evidence.map((item) => (
                    <div className="evidence-item" key={item.id}>
                      <div className="ev-head">
                        <span>{item.evidence_type}</span>
                        <span>·</span>
                        <span className="mono">{item.source_ref}</span>
                        {item.page_number ? <span>· page {item.page_number}</span> : null}
                      </div>
                      {item.excerpt ? <div className="ev-excerpt">{item.excerpt}</div> : null}
                      <div className="ev-explanation">{item.explanation}</div>
                    </div>
                  ))}
                </>
              ) : (
                <p className="small dim mt-8">No separate evidence rows for this indicator.</p>
              )}
            </Collapsible>
          ))
        )}
      </section>
    </>
  )
}

function EvidenceTab({ analysis }: { analysis: AnalysisBundle | null }) {
  const rows = analysis
    ? analysis.findings.flatMap((finding) =>
        finding.evidence.map((item) => ({ ...item, findingTitle: finding.title, severity: finding.severity })),
      )
    : []

  if (!analysis) {
    return (
      <section className="card">
        <EmptyState
          icon={<FileSearch size={24} />}
          title="No evidence recorded"
          message="Evidence rows are created during analysis. Run the analysis first to see the sources behind each indicator."
        />
      </section>
    )
  }

  return (
    <section className="card">
      <div className="card-head">
        <h3>
          <FileSearch size={16} /> Evidence traceability
        </h3>
        <span className="card-hint">{rows.length} evidence rows</span>
      </div>

      <div className="disclaimer" style={{ marginBottom: 14 }}>
        <span>
          Each row links a finding to the exact metadata field or page text that produced it, so
          every conclusion can be traced back to its source.
        </span>
      </div>

      {rows.length === 0 ? (
        <EmptyState
          icon={<FileSearch size={24} />}
          title="No evidence yet"
          message="Indicators with supporting sources will appear here after analysis."
        />
      ) : (
        rows.map((item) => (
          <div className="evidence-item" key={item.id} style={{ borderLeftColor: severityColor(item.severity) }}>
            <div className="ev-head">
              <SeverityBadge severity={item.severity} />
              <span className="mono">{item.source_ref}</span>
              <span>· {item.evidence_type}</span>
              {item.page_number ? <span>· page {item.page_number}</span> : null}
            </div>
            <div className="finding-title" style={{ marginBottom: 6 }}>
              {item.findingTitle}
            </div>
            {item.excerpt ? <div className="ev-excerpt">{item.excerpt}</div> : null}
            <div className="ev-explanation">{item.explanation}</div>
          </div>
        ))
      )}
    </section>
  )
}

function severityColor(severity: string): string {
  if (severity === 'high') return 'var(--danger)'
  if (severity === 'medium') return 'var(--warning)'
  if (severity === 'low') return 'var(--info)'
  return 'var(--text-dim)'
}
