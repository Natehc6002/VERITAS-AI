// Formatting helpers shared across the UI.

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return '—'
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB']
  let value = bytes / 1024
  let unitIndex = 0
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024
    unitIndex += 1
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[unitIndex]}`
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
  })
}

export function shortHash(hash: string): string {
  if (!hash) return '—'
  return `${hash.slice(0, 12)}…${hash.slice(-6)}`
}

export function plural(count: number, singular: string, pluralForm?: string): string {
  return count === 1 ? singular : (pluralForm ?? `${singular}s`)
}

export function pageRangeLabel(page: number, pageSize: number, total: number): string {
  if (total === 0) return '0 results'
  const start = (page - 1) * pageSize + 1
  const end = Math.min(page * pageSize, total)
  return `${start}–${end} of ${total}`
}

export const ENTITY_TYPE_LABELS: Record<string, string> = {
  person_name: 'Person',
  organization: 'Organization',
  date: 'Date',
  money: 'Amount',
  email: 'Email',
  phone: 'Phone',
  document_identifier: 'Identifier',
  url: 'URL',
}

export const CATEGORY_LABELS: Record<string, string> = {
  invoice: 'Invoice',
  receipt: 'Receipt',
  certificate: 'Certificate',
  identity_document: 'Identity document',
  financial_statement: 'Financial statement',
  contract: 'Contract',
  report: 'Report',
  other: 'Other',
}

export const FINDING_CATEGORY_LABELS: Record<string, string> = {
  missing_metadata: 'Missing metadata',
  exif_metadata_present: 'EXIF metadata present',
  timestamp_anomaly: 'Timestamp anomaly',
  producer_anomaly: 'Producer anomaly',
  empty_or_sparse_text: 'Sparse text',
  inconsistent_dates: 'Inconsistent dates',
  conflicting_identifiers: 'Conflicting identifiers',
  duplicate_file: 'Duplicate file',
}
