---
description: Standards for designing React/Next components in Alpha Tales. Apply when creating or refactoring UI to guarantee accessibility, variant safety, and clean separation between server & client logic.
globs:
alwaysApply: false
---

# Component-Design Standards

## Critical Rules

- If this is applied, please add a comment to the top of the page "Component standards rule applied"
- **Name & file** – One component per file, Pascal-cased export (`Button.tsx`).
- **Single-responsibility** – UI only: **move all business or stateful logic into custom hooks** (`use*`). Components compose hooks and render UI.
- **Server vs Client** – Default to Server Components; add `"use client"` only for required interactivity.
- **React Compiler** – Let React 19's compiler handle memoization automatically. Avoid manual `useMemo`/`useCallback` unless profiler confirms need.
- **Variants** – Use `class-variance-authority` (`cva`) with default variants; never build variants by string-concatenating classes.
- **Class names** – Build with `cn()` / `clsx`; Prettier + `prettier-plugin-tailwindcss` auto-sorts, ESLint extends `plugin:tailwindcss/recommended`.
- **Accessibility** – Every interactive element needs `focus-visible:ring-2` (or equivalent) and WCAG ≥ 4.5 : 1 contrast in light & dark themes.
- **ARIA roles** – Provide correct roles / `aria-*` attributes; modals require `role="dialog"` and `aria-modal="true"`.
- **Tests** – Vitest + React-Testing-Library test per component; include `jest-axe` "no violations" assertion.
- **Image usage** – Use `next/image` with explicit dimensions or `fill` plus Tailwind classes.
- **Exports** – Barrel-export components from their feature folder `index.ts` for easy imports.

---

## Server vs Client Components (React 19)

### Server Components (Default)

```tsx
// app/projects/ProjectList.tsx - Server Component (no directive needed)
import { getProjects } from '@/lib/dal/projects'

export default async function ProjectList() {
  const projects = await getProjects() // Auth verified in DAL
  return (
    <ul>
      {projects.map(p => <li key={p.id}>{p.name}</li>)}
    </ul>
  )
}
```

**Use Server Components for:**
- Data fetching
- Accessing backend resources directly
- Keeping sensitive data on the server
- Large dependencies that shouldn't ship to client

### Client Components

```tsx
// components/ProjectForm.tsx
'use client'

import { useActionState } from 'react'
import { createProject } from '@/app/actions/projects'

export function ProjectForm() {
  const [state, formAction] = useActionState(createProject, null)

  return (
    <form action={formAction}>
      <input name="name" required />
      <button type="submit">Create</button>
      {state?.error && <p className="text-red-500">{state.error}</p>}
    </form>
  )
}
```

**Use `"use client"` only for:**
- Event handlers (onClick, onChange, etc.)
- `useState`, `useEffect`, `useRef` hooks
- Browser APIs (window, document)
- Third-party client libraries

---

## React 19 Compiler (Automatic Memoization)

React 19's compiler handles memoization automatically. Remove excessive manual optimization:

```tsx
// BEFORE (unnecessary with React 19 Compiler)
const filteredItems = useMemo(() => items.filter(i => i.active), [items])
const handleClick = useCallback(() => onClick(id), [onClick, id])

// AFTER (let compiler handle it)
const filteredItems = items.filter(i => i.active)
const handleClick = () => onClick(id)
```

**When to still use manual memoization:**
- React DevTools Profiler confirms specific performance issue
- Complex calculations taking > 16ms
- Callbacks passed to non-React libraries expecting stable references

---

## Server Actions in Components

```tsx
// components/DeleteButton.tsx
'use client'

import { useTransition } from 'react'
import { deleteProject } from '@/app/actions/projects'

export function DeleteButton({ projectId }: { projectId: string }) {
  const [isPending, startTransition] = useTransition()

  return (
    <button
      onClick={() => startTransition(() => deleteProject(projectId))}
      disabled={isPending}
      className="text-red-600 disabled:opacity-50"
    >
      {isPending ? 'Deleting...' : 'Delete'}
    </button>
  )
}
```

---

## Folder Layout

```
src/
└─ features/
   └─ cards/
      ├─ Card.tsx           # UI only (Server or Client)
      ├─ Card.test.tsx      # RTL + axe tests
      ├─ card.variants.ts   # cva variant map
      ├─ hooks.ts           # feature hooks (logic/state)
      └─ index.ts           # export * from './Card'
```

---

## Variant Pattern (CVA)

```ts
// card.variants.ts
import { cva } from 'class-variance-authority'

export const cardVariants = cva(
  'rounded-lg shadow-md transition-colors',
  {
    variants: {
      intent: {
        info:  'bg-blue-50 text-blue-900',
        warn:  'bg-yellow-50 text-yellow-900',
        error: 'bg-red-50 text-red-900',
      },
      size: { sm: 'p-2', md: 'p-4', lg: 'p-8' },
    },
    defaultVariants: { intent: 'info', size: 'md' },
  }
)
```

---

## Accessibility Checklist

| Check | Implementation |
|-------|----------------|
| Focus ring | `focus-visible:outline-none focus-visible:ring-2` |
| Keyboard navigation | Ensure correct `tabIndex`; arrow-key support for lists |
| ARIA for modals | `role="dialog" aria-modal="true"` plus focus return |
| Colour contrast | Test via `jest-axe` or Lighthouse |

---

## Testing Pattern

```ts
import { render, screen } from '@testing-library/react'
import { axe } from 'jest-axe'
import { Card } from './Card'

it('renders accessible card', async () => {
  const { container } = render(<Card title="Hi" />)
  expect(await axe(container)).toHaveNoViolations()
  expect(screen.getByRole('heading', { name: /hi/i })).toBeInTheDocument()
})
```

---

## Examples

<example>
✅ Correct Pattern
```tsx
// Server Component with proper composition
// app/projects/page.tsx
import { getProjects } from '@/lib/dal/projects'
import { ProjectList } from '@/features/projects'

export default async function ProjectsPage() {
  const projects = await getProjects()
  return <ProjectList projects={projects} />
}

// Client Component for interactivity
// features/projects/ProjectForm.tsx
'use client'

import { useActionState } from 'react'
import { createProject } from '@/app/actions/projects'
import { Button } from '@/components/ui/button'
import { cardVariants } from './card.variants'

export function ProjectForm() {
  const [state, formAction] = useActionState(createProject, null)
  return (
    <form action={formAction} className={cardVariants({ intent: 'info' })}>
      <input name="name" className={cn('rounded', 'p-2')} />
      <Button type="submit">Create</Button>
    </form>
  )
}
```
</example>

<example type="invalid">
❌ Incorrect Pattern
```tsx
// Component mixes API calls, state and UI
'use client'
export function BadProjectList() {
  const [projects, setProjects] = useState([])

  // Don't fetch in useEffect - use Server Components!
  useEffect(() => {
    fetch('/api/projects').then(r => r.json()).then(setProjects)
  }, [])

  // Unnecessary manual memoization (compiler handles it)
  const filteredProjects = useMemo(() =>
    projects.filter(p => p.active), [projects])

  // Building classes via string concatenation
  return <div className={'p-' + size}>...</div>
}
```
</example>

---

## Anti-Patterns

- ❌ Component mixes API calls, state, and UI
- ❌ `"use client"` on components without interactivity
- ❌ Manual `useMemo`/`useCallback` without profiler evidence
- ❌ Building classes via string concatenation instead of `cva` or `cn()`
- ❌ Fetching data in `useEffect` instead of Server Components
- ❌ Missing focus outline; fails Lighthouse a11y audit
- ❌ Business logic in Client Components
