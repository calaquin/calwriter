# Frontend Architecture

CalWriter's frontend is a Single-Page Application (SPA) built with React 19, TypeScript, and Vite.

---

## Technology Stack

- **Framework**: React 19 (Functional components, Hooks)
- **Language**: TypeScript (`~6.0.2` with strict typing)
- **Build Tool / Bundler**: Vite (`^8.2.0`)
- **State & Server Cache**: TanStack React Query (`^5.101.4`)
- **Routing**: React Router DOM (`^7.18.2`)
- **Linter**: Oxlint (`^1.75.0`)
- **Text Differencing**: `diff` (`^9.0.0`)

---

## Component Architecture

- **Rich-Text Editor**:
  - ContentEditable-based rich text editor with autosaving debounce.
  - Unified Undo/Redo history tracking that reliably captures formatting, markdown auto-conversions (`- `, `1. `, `[] `), indentations, and text changes.
  - Telemetry tracking: differentiates typed words from pasted text, measures active typing duration, and computes real-time WPM when sample size is sufficient.
- **Hierarchical Sidebar & Navigation**:
  - Drag-and-drop hierarchy reordering for books, sub-folders, and nested chapters.
  - Contextual action menus (`⋯`) with settings, stats, and sharing shortcuts.
- **Search 2.0**:
  - Real-time scoped search (Workspace, Book, Folder) with substring matching, keyword highlighting, and direct deep-linking into chapter prose and notes.
- **Stats & Visualizations**:
  - Interactive heatmaps, word count velocity charts, recurring goal progress rings, and historical goal performance graphs.

---

## Development Server & API Proxy

During development, the Vite server runs on port 5173 inside a container or locally on the host. It proxies all `/api/*` traffic directly to the backend on `http://app:5000` (or `http://localhost:5000`), avoiding CORS issues and mirroring the production single-origin routing behavior.

