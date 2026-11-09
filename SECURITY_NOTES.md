# VERITAS AI — Security Notes

Scope: the VERITAS AI codebase as shipped for a **local hackathon demo**. This document
describes what is enforced, what is deliberately accepted for the demo, and what must
change before any real deployment.

---

## 1. What is implemented and enforced

### Passwords
- **PBKDF2-HMAC-SHA256**, 390,000 iterations, unique 16-byte salt per password
  (`backend/app/core/security.py`). Stored format: `pbkdf2_sha256$<iterations>$<salt>$<hash>`.
- Verification uses `hmac.compare_digest` (constant time).
- Registration enforces a **minimum 8-character password** and a validated email format.
- Login is **timing-equalised**: an unknown email still performs a real PBKDF2
  verification against a dummy hash, and the response is always
  `Invalid email or password.` — no user enumeration by message or by timing
  (`backend/app/services/auth_service.py`).

### Access tokens
- Stateless tokens: `v1.<base64url(payload)>.<base64url(HMAC-SHA256 signature)>`.
- Payload carries `sub` (user id) and `exp` (expiry; default 12 hours, configurable via
  `ACCESS_TOKEN_TTL_MINUTES`).
- Signature verified with constant-time comparison; expiry, token version and subject
  are all checked. Tampered, malformed, forged or expired tokens are rejected with `401`.
- Every API request (except health, register, login) requires a valid bearer token.

### Authorization / data isolation
- Every document, extraction, analysis, comparison and report lookup resolves through
  an owner check: **foreign or missing resources return `404`** — no existence leak
  across accounts (`require_document`, investigation services).
- Dashboard statistics and duplicate-file detection are scoped to the signed-in user.
- Investigation CRUD and the PDF report download are owner-scoped; the report endpoint
  refuses documents the caller does not own.
- Multi-user isolation is covered by the test suite (`tests/test_isolation.py`).

### File upload
- Extension allow-list: `.pdf .png .jpg .jpeg` only.
- **Magic-byte signature checks** (`%PDF-`, PNG, JPEG) server-side — the client-provided
  `Content-Type` is never trusted.
- Streaming upload with a hard **20 MB** cap; partial files are deleted on any failure.
- Storage names are **server-generated UUIDs** — original filenames never become paths
  and are never used to serve files.
- SHA-256 computed for every stored file (also used for duplicate detection).
- Upload directory sits outside the web root and is not exposed by any static route.

### Responses, errors and logging
- `UserResponse` never exposes `password_hash`.
- Unhandled exceptions return a generic `500` body; stack traces go to the server log
  only, never to the client.
- Domain errors return `{"detail": "…"}` with the proper status code.
- Report download filenames are sanitised to `[A-Za-z0-9-_.]` before being placed in the
  `Content-Disposition` header (no header injection).
- CORS is an explicit origin allow-list (default `http://localhost:5173`), never `*`.

### Repository hygiene (verified)
- No credentials, tokens, passwords or private keys are present in any tracked file or
  in Git history (searched: `live-demo`, `password=`/`secret=` literals — none found).
- `backend/.env`, `*.db`, `uploads/`, `*.log`, `.venv/` are all **git-ignored**;
  only `.env.example` (placeholder values, no secrets) is tracked.
- No `backend/.env` exists in this checkout — configuration comes from defaults or
  environment variables.

---

## 2. Demo-account policy

- The demo database (`backend/veritas.db`) is **local and git-ignored**. Any account
  that exists there (including any pre-created demo account) exists only on this
  machine's working copy — its credentials are **never** written into this repository,
  the documentation, commits or logs.
- **Recommended for the demo: register a fresh account live** (it takes seconds and
  demonstrates the auth flow). See [DEMO_GUIDE.md](DEMO_GUIDE.md).
- Never reuse a real/personal password for demo accounts. The demo account, if present,
  is for this local instance only.

---

## 3. Accepted risks for a local demo (not yet mitigated)

| Risk | Status | Why accepted here |
|---|---|---|
| No login rate limiting / lockout | Known gap | Local-only demo; add before internet exposure |
| HTTP on localhost | Known gap | Loopback traffic only; TLS terminates at a reverse proxy in production |
| Token stored in `localStorage` | Known gap | Simple demo UX; production should use `httpOnly`+`Secure` cookies with CSRF protection |
| Ephemeral signing key when `AUTH_SECRET_KEY` is unset | Known gap | Keys are per-process; a restart invalidates sessions (users just sign in again). Set `AUTH_SECRET_KEY` to persist sessions |
| SQLite file database | Known gap | Single-user demo scale; production should use a real DB server |
| Synchronous request processing | Known gap | ≤20 MB files; see [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) |
| No password reset / email verification | Known gap | Out of scope for the demo |

---

## 4. Before any real deployment

1. Set a strong `AUTH_SECRET_KEY` (environment variable, never committed).
2. Serve behind HTTPS; enable secure cookie delivery if switching to cookies.
3. Add rate limiting on `/auth/login` and `/auth/register`.
4. Move to a production database; back it up.
5. Enable request auditing and centralised log shipping; review log retention.
6. Re-run the test suite and an external penetration test.

---

## 5. Reporting

Security concerns in this repository: use the GitHub issue tracker of the project or
contact the repository owner. **Do not open issues containing real credentials.**
