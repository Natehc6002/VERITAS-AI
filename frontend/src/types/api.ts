// Types mirroring the VERITAS AI backend response schemas.

export interface DocumentRecord {
  id: string
  original_filename: string
  file_extension: string
  mime_type: string
  file_size: number
  sha256_hash: string
  upload_timestamp: string
  processing_status: string
  page_count: number | null
  pdf_metadata: PdfMetadata | null
  investigation_id?: string | null
}

export interface PdfMetadata {
  page_count?: number
  metadata?: Record<string, string>
}

export interface DocumentListResponse {
  items: DocumentRecord[]
  total: number
  page: number
  page_size: number
}

export interface HealthResponse {
  status: string
}

export interface PageText {
  page_number: number
  text: string
  char_count: number
  word_count: number
  method: string
  confidence: number | null
}

export interface ExtractionResponse {
  document_id: string
  status: string
  method: string
  page_count: number | null
  char_count: number
  word_count: number
  ocr_available: boolean
  error: string | null
  pages: PageText[]
}

export interface EntityRecord {
  id: string
  entity_type: string
  value: string
  normalized_value: string | null
  confidence: number | null
  page_number: number | null
  source_text: string | null
}

export interface EvidenceRecord {
  id: string
  page_number: number | null
  evidence_type: string
  source_ref: string
  excerpt: string | null
  explanation: string
}

export interface FindingRecord {
  id: string
  category: string
  severity: string
  confidence: number | null
  title: string
  explanation: string
  detection_method: string
  page_number: number | null
  created_at: string | null
  evidence: EvidenceRecord[]
}

export interface ClassificationResult {
  status: string
  category?: string | null
  category_label?: string | null
  confidence?: number | null
  rationale?: Array<{ rule: string; category: string; weight: number; matched: string }>
  method?: string | null
}

export interface AnalysisBundle {
  document_id: string
  extraction: ExtractionResponse | null
  classification: ClassificationResult
  summary: string | null
  entities: EntityRecord[]
  findings: FindingRecord[]
  disclaimer: string | null
}

export interface CompareRequest {
  document_ids: string[]
}

export interface SharedEntityOccurrence {
  document_id: string
  document_name: string
  page_number: number | null
  source_text: string | null
  confidence: number | null
}

export interface SharedEntity {
  entity_type: string
  value: string
  normalized_value: string
  document_count: number
  occurrences: SharedEntityOccurrence[]
  explanation: string
  match_type?: 'exact' | 'fuzzy'
  similarity?: number | null
  fuzzy_variant?: string | null
}

export interface RelatedRecord {
  document_ids: string[]
  document_names: string[]
  shared_values: Array<{ entity_type: string; value: string }>
  explanation: string
}

export interface Conflict {
  conflict_type: string
  field: string
  subject?: string | null
  values: Array<{ value: string; documents: Array<Record<string, unknown>> }>
  explanation: string
  severity: string
}

export interface CompareResponse {
  document_ids: string[]
  document_names: string[]
  shared_entities: SharedEntity[]
  related_records: RelatedRecord[]
  conflicts: Conflict[]
  summary: {
    documents_compared: number
    shared_entity_count: number
    related_record_count: number
    conflict_count: number
    fuzzy_match_count?: number
  }
  method: string
  disclaimer: string
}

export interface RecentDocument {
  id: string
  original_filename: string
  file_extension: string
  upload_timestamp: string
  processing_status: string
  file_size: number
}

export interface StatsResponse {
  total_documents: number
  processed_documents: number
  failed_documents: number
  documents_with_text: number
  total_findings: number
  findings_by_severity: Record<string, number>
  total_entities: number
  recent_documents: RecentDocument[]
}

export interface UserRecord {
  id: string
  email: string
  created_at: string
}

export interface InvestigationRecord {
  id: string
  name: string
  description: string | null
  owner_id: string
  created_at: string
  updated_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: UserRecord
  investigation: InvestigationRecord | null
}

export interface AuthContextResponse {
  user: UserRecord
  investigations: InvestigationRecord[]
}
