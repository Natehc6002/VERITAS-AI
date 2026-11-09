# VERITAS AI — Frontend

React 19 + TypeScript + Vite single-page application for the VERITAS AI backend.

- axios (typed API client) · react-router-dom · lucide-react · hand-written design-system CSS

## Run

```powershell
cd frontend
npm run dev
```

Open `http://localhost:5173`. The Vite dev server proxies `/api/*` to
`http://localhost:8000` (see `vite.config.ts`), so no CORS configuration is needed in
development.

## Build / type-check

```powershell
npm run build      # runs `tsc && vite build`
npm run preview    # serve the production build locally
```

## Pages

| Route | Purpose |
|---|---|
| `/` | Dashboard — real statistics (totals, processing state, findings by severity, recent uploads) |
| `/upload` | Drag-and-drop upload with client-side validation, per-file progress, success/failure states |
| `/documents` | Library — server-side search, pagination, sorting, delete confirmation |
| `/documents/:id` | Investigation view — Overview / Extracted text / Analysis / Evidence tabs |
| `/compare` | Pick 2+ documents → shared entities, related records, conflicts |
| `*` | 404 |

## Structure

```
src/
├── components/     primitives (badges, alerts, states), dropzone, table, confirm dialog
├── layouts/        AppShell — sidebar navigation, topbar, backend health indicator
├── pages/          one file per route
├── services/api.ts axios instance + typed API functions + errorMessage() helper
├── styles/         index.css — the whole design system (CSS variables, dark theme)
├── types/api.ts    TypeScript mirrors of backend response schemas
└── utils/format.ts bytes, dates, labels
```

## Conventions

- **No hardcoded API data.** Every value on screen comes from a typed backend call.
- **Errors surface.** `errorMessage()` converts FastAPI validation errors, domain `detail`
  strings, timeouts and connection failures into readable messages with retry controls.
- **Only implemented features are shown.** Pending analysis shows explicit empty states rather
  than placeholder content.
- Type-only imports use `import type` (required by `verbatimModuleSyntax`).
