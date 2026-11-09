import { FileCheck2, Lock, ScanSearch, ShieldCheck } from 'lucide-react'

export function AuthAside({ mode }: { mode: 'login' | 'register' }) {
  return (
    <aside className="auth-aside">
      <div className="aside-inner">
        <div className="sidebar-brand" style={{ marginBottom: 26 }}>
          <span className="brand-mark">
            <ShieldCheck size={19} />
          </span>
          <div>
            <div className="brand-name">VERITAS AI</div>
            <div className="brand-sub">Document forensics</div>
          </div>
        </div>

        <h2>
          {mode === 'login'
            ? 'Evidence analysis you can walk through, line by line.'
            : 'Start with a claim. End with traceable evidence.'}
        </h2>
        <p className="lede">
          VERITAS AI extracts metadata, text and signals from PDFs and images, then shows exactly
          which observation triggered each finding — source page, field and value included.
        </p>

        <div className="auth-points">
          <div className="auth-point">
            <span className="ap-icon">
              <FileCheck2 size={15} />
            </span>
            <span>
              <strong>Signature-validated ingestion</strong>
              Magic-byte checks, SHA-256 hashing and owner-scoped storage from the first upload.
            </span>
          </div>
          <div className="auth-point">
            <span className="ap-icon">
              <ScanSearch size={15} />
            </span>
            <span>
              <strong>Explainable findings</strong>
              Every indicator links back to metadata, page text or a comparison rule — never an
              opaque score.
            </span>
          </div>
          <div className="auth-point">
            <span className="ap-icon">
              <Lock size={15} />
            </span>
            <span>
              <strong>Isolated by account</strong>
              Documents, investigations and reports are accessible only to their owner.
            </span>
          </div>
        </div>
      </div>
    </aside>
  )
}
