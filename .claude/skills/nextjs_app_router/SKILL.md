---
description: Standards for building Next.js 15 apps using the App Router in Alpha Tales. Apply when creating or updating pages, layouts, route handlers, components, or auth logic to ensure scalable, production-ready frontend architecture.
globs:
alwaysApply: false
---

# Next.js App Router Guidelines for Alpha Tales

## Critical Rules

- If this is applied, please add a comment to the top of the page "App router rule applied"
- **Next.js version** - Use **>= 15.2.3** (CVE-2025-29927 fix). Current: 15.1.6 - **upgrade required**.
- **React version** - Using React 19 with automatic compiler optimizations.
- All route logic must live inside the `app/` directory using file-based routing
- Use **Server Components by default** - only add `"use client"` when interactivity is required
- **Data Access Layer** - Verify authentication at every data access point, not just middleware
- Use **Server Actions** with `"use server"` for form mutations instead of API routes
- Use React 19 hooks: `useFormStatus`, `useActionState`, `useOptimistic`
- **React Compiler** handles memoization - avoid manual `useMemo`/`useCallback`
- Implement route protection via middleware AND Data Access Layer (defense-in-depth)

---

## Technology Stack

| Technology | Version | Notes |
|------------|---------|-------|
| Next.js | 15.1.6 -> 15.2.3+ | Upgrade required for CVE fix |
| React | 19.0.0 | Stable with new hooks |
| TypeScript | 5.4.5 | Strict mode enabled |
| Turbopack | Stable | Use for dev and builds |

---

## React 19 Specific Patterns

### Server Actions (Replace API Routes for Mutations)

```ts
// app/actions/projects.ts
'use server'

import { auth } from '@/auth'
import { z } from 'zod'
import { revalidatePath } from 'next/cache'

const schema = z.object({
  name: z.string().min(1).max(100),
  description: z.string().optional(),
})

export async function createProject(formData: FormData) {
  const session = await auth({ ensureSignedIn: true })
  const validated = schema.parse(Object.fromEntries(formData))

  await db.projects.create({
    data: { ...validated, userId: session.user.id }
  })

  revalidatePath('/projects')
  return { success: true }
}
```

### useActionState for Server Action State

```tsx
'use client'

import { useActionState } from 'react'
import { createProject } from '@/app/actions/projects'

function ProjectForm() {
  const [state, formAction, pending] = useActionState(createProject, null)

  return (
    <form action={formAction}>
      <input name="name" required />
      <button disabled={pending}>
        {pending ? 'Creating...' : 'Create Project'}
      </button>
      {state?.error && <p className="text-red-500">{state.error}</p>}
    </form>
  )
}
```

### useFormStatus for Submission State

```tsx
'use client'

import { useFormStatus } from 'react-dom'

function SubmitButton({ children }: { children: React.ReactNode }) {
  const { pending } = useFormStatus()
  return (
    <button type="submit" disabled={pending}>
      {pending ? 'Submitting...' : children}
    </button>
  )
}
```

### useOptimistic for Instant UI Updates

```tsx
'use client'

import { useOptimistic, useTransition } from 'react'

function ProjectList({ projects }: { projects: Project[] }) {
  const [optimisticProjects, addOptimistic] = useOptimistic(
    projects,
    (state, newProject: Project) => [...state, { ...newProject, pending: true }]
  )
  const [_, startTransition] = useTransition()

  async function handleAdd(formData: FormData) {
    const newProject = { id: Date.now(), name: formData.get('name') as string }
    startTransition(() => addOptimistic(newProject))
    await createProject(formData)
  }

  return (
    <ul>
      {optimisticProjects.map(project => (
        <li key={project.id} className={project.pending ? 'opacity-50' : ''}>
          {project.name}
        </li>
      ))}
    </ul>
  )
}
```

---

## React Compiler (Automatic Optimization)

React 19 includes an automatic compiler that handles memoization:

```tsx
// BEFORE (unnecessary with React Compiler)
const expensiveValue = useMemo(() => calculate(data), [data])
const handleClick = useCallback(() => onClick(id), [onClick, id])

// AFTER (let compiler handle it)
const expensiveValue = calculate(data)
const handleClick = () => onClick(id)
```

**When to still use manual memoization:**
- Profiler confirms specific performance issue
- Complex calculations with measured impact
- Callbacks passed to non-React libraries expecting stable references

---

## Data Access Layer Security Pattern

**CRITICAL: Middleware is NOT sufficient for authentication (CVE-2025-29927)**

```ts
// lib/dal/index.ts
import { auth } from '@/auth'
import { cache } from 'react'

export const verifyAuth = cache(async () => {
  const session = await auth()
  if (!session?.user) {
    throw new Error('Unauthorized')
  }
  return session
})

// lib/dal/projects.ts
export async function getProjects() {
  const session = await verifyAuth() // ALWAYS verify
  return db.projects.findMany({ where: { userId: session.user.id } })
}
```

Use DAL in Server Components and Server Actions:

```tsx
// app/projects/page.tsx
import { getProjects } from '@/lib/dal/projects'

export default async function ProjectsPage() {
  const projects = await getProjects() // Auth verified in DAL
  return <ProjectList projects={projects} />
}
```

---

## Turbopack (Production Builds)

Turbopack is now stable for production in Next.js 15.3+:

```bash
# Development (already enabled)
next dev --turbo

# Production builds (2-5x faster)
next build --turbo
```

**Benefits:**
- 2-5x faster builds
- Faster Fast Refresh (5-10x)
- Incremental builds with caching
- Better parallelization across CPU cores

---

## Folder and File Organization

```
app/
├── (app)/                    # Protected routes group
│   ├── projects/
│   │   ├── page.tsx         # List projects
│   │   ├── [id]/
│   │   │   └── page.tsx     # Project detail
│   │   └── loading.tsx      # Loading state
│   ├── settings/
│   └── layout.tsx           # Auth layout
├── auth/                     # Public auth routes
│   ├── login/
│   └── signup/
├── api/                      # API routes (prefer Server Actions)
│   └── health/
├── actions/                  # Server Actions
│   ├── projects.ts
│   └── users.ts
├── layout.tsx               # Root layout
└── providers.tsx            # Global providers
```

**Rules:**
- ✅ Place all routes inside `app/` directory
- ✅ Use `layout.tsx` for shared structure, `page.tsx` for content
- ✅ Group related routes with `()` syntax (doesn't affect URL)
- ✅ Colocate Server Actions in `app/actions/`
- ❌ Do not use deprecated `pages/` directory

---

## Server vs Client Components

### Server Components (Default)

```tsx
// app/projects/page.tsx - Server Component (no directive needed)
import { getProjects } from '@/lib/dal/projects'

export default async function ProjectsPage() {
  const projects = await getProjects()
  return <ProjectList projects={projects} />
}
```

### Client Components (When Needed)

```tsx
// components/ProjectForm.tsx
'use client'

import { useState } from 'react'
import { useActionState } from 'react'

export function ProjectForm() {
  const [name, setName] = useState('')
  // Client-side interactivity required
}
```

**Use `"use client"` only for:**
- `useState`, `useEffect`, `useRef` hooks
- Event handlers (onClick, onChange, etc.)
- Browser APIs (window, document)
- Third-party client libraries

---

## Route Handlers vs Server Actions

### Prefer Server Actions for Mutations

```ts
// app/actions/projects.ts
'use server'

export async function createProject(formData: FormData) {
  const session = await auth({ ensureSignedIn: true })
  // Create project...
  revalidatePath('/projects')
}
```

### Use Route Handlers for:

- Webhooks from external services
- File uploads with streaming
- Third-party API integrations
- Non-form mutations from external clients

```ts
// app/api/webhooks/stripe/route.ts
export async function POST(request: Request) {
  const body = await request.text()
  const signature = request.headers.get('stripe-signature')!
  // Handle webhook...
}
```

---

## Caching and Revalidation

### Upcoming: 'use cache' Directive

```tsx
// Future pattern (Next.js 15.3+)
async function getData() {
  'use cache'
  return fetch('https://api.example.com/data').then(r => r.json())
}
```

### Current Patterns

```tsx
// Time-based revalidation
export const revalidate = 60 // Revalidate every 60 seconds

// On-demand revalidation
import { revalidatePath, revalidateTag } from 'next/cache'

revalidatePath('/projects')
revalidateTag('projects')
```

---

## Performance and Optimization

- ✅ Use `next/dynamic` for code-splitting heavy components
- ✅ Use `<Suspense>` with `loading.tsx` for streaming
- ✅ Use `next/image` for responsive, optimized images (WebP/AVIF auto-detection)
- ✅ Let React Compiler handle memoization
- ✅ Use Server Actions instead of API routes for mutations
- ✅ Enable Turbopack for faster builds

```tsx
// Dynamic import for heavy component
import dynamic from 'next/dynamic'

const HeavyChart = dynamic(() => import('@/components/HeavyChart'), {
  loading: () => <ChartSkeleton />,
})
```

---

## Authentication and Route Protection

### Defense-in-Depth (Required)

```
1. Middleware      - First line of defense
2. Data Access Layer - ALWAYS verify auth (REQUIRED)
3. Row-level security - Database level (recommended)
```

### Middleware Configuration

```ts
// middleware.ts
import { authkitMiddleware } from '@workos-inc/authkit-nextjs'

export default authkitMiddleware({
  middlewareAuth: {
    enabled: true,
    unauthenticatedPaths: PUBLIC_PATHS,
  },
})
```

### Data Access Layer (Required)

```ts
// lib/dal/projects.ts
import { verifyAuth } from './index'

export async function getProjects() {
  const session = await verifyAuth() // Always verify!
  return db.projects.findMany({ where: { userId: session.user.id } })
}
```

---

## Examples

<example>
✅ Modern Server Component with Server Action
```tsx
// app/projects/page.tsx
import { getProjects } from '@/lib/dal/projects'
import { ProjectForm } from '@/components/ProjectForm'

export default async function ProjectsPage() {
  const projects = await getProjects() // Auth verified in DAL
  return (
    <div>
      <h1>Projects</h1>
      <ProjectForm />
      <ul>
        {projects.map(p => <li key={p.id}>{p.name}</li>)}
      </ul>
    </div>
  )
}
```
</example>

<example>
✅ Client Component with useActionState
```tsx
'use client'
import { useActionState } from 'react'
import { useFormStatus } from 'react-dom'
import { createProject } from '@/app/actions/projects'

function SubmitButton() {
  const { pending } = useFormStatus()
  return <button disabled={pending}>{pending ? 'Creating...' : 'Create'}</button>
}

export function ProjectForm() {
  const [state, formAction] = useActionState(createProject, null)
  return (
    <form action={formAction}>
      <input name="name" required />
      <SubmitButton />
      {state?.error && <p className="text-red-500">{state.error}</p>}
    </form>
  )
}
```
</example>

<example type="invalid">
❌ Old Pattern (Avoid)
```tsx
'use client'
export default function ProjectsPage() {
  const [projects, setProjects] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/projects')
      .then(r => r.json())
      .then(setProjects)
      .finally(() => setLoading(false))
  }, [])

  // Don't fetch in useEffect - use Server Components!
}
```
</example>

<example type="invalid">
❌ Missing DAL Verification
```tsx
// WRONG: Only middleware protection
export default async function ProjectsPage() {
  // Middleware might be bypassed (CVE-2025-29927)
  const projects = await db.projects.findMany()
  return <ProjectList projects={projects} />
}
```
</example>

---

## Anti-Patterns

- ❌ Using `useEffect` for data fetching (use Server Components)
- ❌ Relying only on middleware for authentication
- ❌ Manual `useMemo`/`useCallback` without profiler evidence
- ❌ API routes for form mutations (use Server Actions)
- ❌ `"use client"` on components without interactivity
- ❌ Business logic in Client Components
- ❌ Accessing `process.env` in Client Components
- ❌ Using deprecated `pages/` directory
