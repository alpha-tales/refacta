---
name: refactor_rules
version: 0.1.0
description: >
  Central refactor rulebook for this project. Defines how code should be
  transformed, which patterns are allowed/forbidden, and how to apply
  multi-pass refactors safely without changing functionality.
---

# Refactor Rules Skill

You are the canonical rulebook for all refactoring in this project.
Any agent that loads this Skill **must** treat these rules as hard constraints,
not suggestions.

**Top-level goals:**
1. Improve code quality, structure, and consistency
2. Avoid changing behaviour unless a rule explicitly allows it
3. Keep changes explainable, minimal, and reversible
4. Always prefer clarity and maintainability over cleverness

---

## 1. General Principles

- Do not alter public APIs (function signatures, HTTP contract, exported component props)
  unless the rule explicitly permits it for that pass.
- Prefer small, incremental refactors over large sweeping rewrites.
- Avoid unnecessary abstraction; only introduce new abstractions if they clearly reduce
  duplication or complexity.
- Do not delete logic unless it is provably dead (unreachable and unreferenced).
- Keep changes local to the current pass: don't opportunistically "fix other stuff"
  that's outside the defined scope.

When in doubt:
- Ask via comments/notes instead of making assumptions.
- Leave TODO comments only when strictly necessary; avoid generating TODO clutter.

---

## 2. Next.js / React Frontend Rules

### 2.1 File structure & naming
- Prefer the `app/` directory over `pages/` for new work if the project has already
  migrated to the App Router.
- Component files:
  - Use `PascalCase` for React components: `UserProfile.tsx`
  - Use `camelCase` for hooks: `useUserProfile.ts`
  - Co-locate component, styles, and test files when feasible.

### 2.2 Component patterns
- Prefer functional components with hooks; do not introduce class components.
- Hooks must follow the Rules of Hooks (top-level, consistent ordering).
- Avoid inline anonymous components inside JSX trees unless trivial.
- Prefer explicit props interfaces:
```ts
interface UserCardProps {
  userId: string;
}
```
over `any` or implicit props.

### 2.3 Imports & dependencies
- Use path aliases (if configured) instead of deep relative imports.
- Remove unused imports and re-exports.
- Avoid adding new external dependencies unless explicitly allowed by the rules for that pass.

---

## 3. Python Backend Rules

### 3.1 Structure
- Maintain existing service boundaries (services/, repositories/, api/, etc.).
- Do not move modules across layers unless explicitly instructed.
- Keep business logic out of API/route handlers where possible; push it into services.

### 3.2 Code style
- Prefer type hints for new or modified functions.
- Use ruff / black-style conventions for formatting and imports where applicable.
- Do not introduce complex metaprogramming or magic patterns.
- Use `snake_case` for variables and functions.
- Use descriptive names that explain purpose.
- Boolean variables should start with `is_`, `has_`, `can_`.

### 3.3 Error handling
- Replace broad `except Exception` with more specific exceptions when clearly identifiable.
- Preserve existing error semantics; don't change error types unless instructed.
- Use specific exception types, not bare `except:`.
- Add meaningful error messages.

### 3.4 Modern Python Features
- Use f-strings instead of `.format()` or `%`.
- Use pathlib instead of os.path.
- Use context managers (`with`) for resources.
- Use list/dict comprehensions when readable.
- Use dataclasses for data structures.

---

## 4. Multi-Pass Refactor Protocol

The orchestrator will trigger multiple passes. On each pass:

### Pass 1 - Structural cleanup
- Remove dead code, unused imports, unused variables.
- Normalize simple patterns (consistent imports, basic formatting).
- No behavioural changes.

### Pass 2 - Local refactors
- Extract small helpers, simplify conditionals, inline trivial intermediates.
- Improve naming for clarity (variables, functions, components) without changing public API.

### Pass 3 - Cross-file consistency
- Align patterns across similar modules/components.
- Ensure repeated structures follow a single canonical pattern.

**For each pass:**
- Always explain what you changed and why in the log output.
- Reference which rules you applied.

---

## 5. Forbidden Actions

Unless explicitly allowed by a rule, **do not**:
- Change environment variable names or meanings.
- Change config files that affect deployment or infra.
- Introduce new third-party dependencies.
- Change database schemas or migrations.
- Modify CI/CD configuration.

If a requested change would violate these constraints:
- Explain why and propose an alternative in the report instead of applying it.

---

## 6. Code Smells to Avoid

- Long functions (> 50 lines)
- Long parameter lists (> 4 parameters)
- Deeply nested conditionals (> 3 levels)
- Magic numbers (use named constants)
- Dead code (delete it!)
- Commented-out code (use version control)

---

## 7. Security Rules

- Never hardcode secrets.
- Validate all inputs.
- Use parameterized queries (prevent SQL injection).
- Sanitize user data.
- Keep dependencies updated.
