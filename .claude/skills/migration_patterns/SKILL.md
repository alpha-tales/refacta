---
name: migration_patterns
version: 0.1.0
description: >
  Patterns and mapping rules for framework or platform migrations
  (e.g., Xamarin to React Native). Not used in the initial MVP but
  reserved for future migration workflows.
---

# Migration Patterns Skill

This Skill describes high-level migration strategies between stacks while preserving behaviour.
For now, it documents the conceptual mapping; concrete patterns can be filled in later.

---

## 1. General Migration Principles

- Preserve user-facing behaviour and APIs as much as possible.
- Prefer incremental migration (module by module) over big-bang rewrites.
- Keep feature parity as the primary constraint; refactoring for elegance is secondary.
- Retain test coverage (or add tests) to prove parity.

---

## 2. Example: Xamarin to React Native

### 2.1 UI Mapping
- Xamarin pages/views -> React Native screen components.
- XAML layouts -> JSX/TSX layout with appropriate styling primitives.
- ViewModels -> React hooks + state management (Context / Redux / React Query / existing patterns).

### 2.2 Navigation
- Xamarin navigation stack -> React Navigation (or project-standard navigation lib).
- Keep route names and parameter signatures consistent where possible.

### 2.3 Data/API Layer
- Shared API clients should be extracted into a common JS/TS layer.
- Preserve endpoint contracts: URLs, payload shapes, error semantics.

---

## 3. Migration Workflow Template

1. **Scan** the existing module and generate a functional map:
   - Screens
   - ViewModels / Controllers
   - API calls
   - Navigation flows

2. **Propose** a React Native module structure:
   - Screens
   - Hooks
   - Components
   - Shared utilities

3. **Generate** scaffold React Native code:
   - Empty, but structured with correct props and navigation.

4. **Port** logic in small, testable chunks.

5. **Run** parity checks:
   - Compare UI flow
   - Compare API usage
   - Compare error flows

**Agents must never "half-migrate" without clearly documenting what is missing.**

---

## 4. Language/Framework Mapping Reference

| Source | Target | Notes |
|--------|--------|-------|
| C# classes | TypeScript interfaces/classes | Preserve property names |
| XAML bindings | React state/props | Map observable patterns |
| async/await (C#) | async/await (JS) | Similar semantics |
| LINQ | Array methods | map/filter/reduce |
| Dependency Injection | React Context / custom hooks | Invert control patterns |

---

## 5. Future Enhancements

- Automated scaffold generation
- Parity test generation
- Visual diff tooling for UI comparison
- API contract validation
