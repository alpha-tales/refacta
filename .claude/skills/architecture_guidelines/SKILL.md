---
name: architecture_guidelines
version: 0.1.0
description: >
  Describes high-level architectural boundaries and conventions for this
  project (frontend + backend). Guides scanners and refactorers so they
  do not break layering or ownership.
---

# Architecture Guidelines Skill

You define how the project is structured and how responsibilities are divided.
Agents using this Skill must:
- Respect boundaries between layers
- Avoid coupling unrelated modules
- Preserve the intent of existing architecture decisions

---

## 1. High-Level Overview

The project typically follows this structure:

- `frontend/` or `web/`
  - Next.js App/Pages
  - Components, hooks, layouts, API clients
- `backend/` or `api/`
  - HTTP handlers / controllers
  - Services / use-cases
  - Repositories / data access
  - Domain models
- `shared/` or `lib/`
  - Utilities and shared types
  - Cross-cutting helpers

If a concrete repo differs, infer its structure from directory names and patterns and
stick to the spirit of these guidelines.

---

## 2. Frontend (Next.js) Architecture

- Keep UI components:
  - **Presentational components**: minimal logic, mostly props + rendering.
  - **Container components**: can coordinate data fetching and state.
- Data fetching:
  - Prefer project's existing pattern (hooks, React Query, server components, etc.).
  - Do not introduce new data-fetching libraries.
- Routing:
  - Respect existing route layout; don't change URL structure unless explicitly instructed.

---

## 3. Backend (Python) Architecture

**Typical layering (customize as needed):**

- `api/`:
  - HTTP routes, FastAPI/Flask views, etc.
  - Thin controllers delegating to services.
- `services/`:
  - Business-use-case orchestration.
  - Transaction boundaries.
- `repositories/` or `db/`:
  - Direct database access; ORM/session management.
- `domain/`:
  - Domain entities, value objects, domain logic.

**Rules:**
- Controllers must not contain complex business logic.
- Services must not contain direct SQL/ORM logic; delegate to repositories.
- Domain objects should not depend on infrastructure modules.

---

## 4. Cross-Cutting Concerns

- **Logging:**
  - Use existing logging library and patterns.
  - Avoid printing to stdout directly in production code.
- **Configuration:**
  - Respect existing config loader (env vars, config files).
  - Do not hard-code secrets or environment-specific values.
- **Error handling:**
  - Keep consistent error mapping from backend to frontend where applicable.

---

## 5. How Agents Should Use This Skill

### project-scanner
- Uses these rules to classify files into layers and modules.
- Builds a manifest that preserves these structural distinctions.

### nextjs-refactorer / python-refactorer
- Avoid moving code across layers unless a rule explicitly instructs it.
- When introducing helpers or modules, choose appropriate layer based on these rules.

**If unsure, agents should:**
- Prefer to keep code where it is.
- Document ambiguity in the report rather than guessing.

---

## 6. Token Efficiency Guidelines

To minimize API costs and improve performance:

- **Summarize large files**: When processing large files, create structured summaries
  instead of sending entire file contents.
- **Batch similar operations**: Group related file operations together.
- **Use targeted reads**: Read only the specific sections of files needed for the task.
- **Cache intermediate results**: Store manifest and analysis results to avoid re-processing.
- **Limit context**: Only include relevant context in prompts, not entire codebase.
