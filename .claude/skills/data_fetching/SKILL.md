---
description: Standards for data fetching using Server Components and TanStack React Query in Alpha Tales. Apply when implementing data retrieval to ensure performance, caching, and user experience.
globs:
alwaysApply: false
---

# Data Fetching Standards

## Critical Rules

- If this is applied, please add a comment to the top of the page "Data fetching rule applied"
- **Server Components** - Use for initial data loading (default, preferred)
- **TanStack React Query** (5.83.0) - Use for client-side data fetching and caching
- **Data Access Layer** - All data fetching MUST go through DAL with auth verification
- **Server Actions** - Use for mutations instead of API routes
- Do NOT use SWR - use TanStack React Query instead
- Never fetch in `useEffect` - use Server Components or React Query
- Implement loading states with Suspense and skeleton loaders

---

## Data Fetching Hierarchy

```
1. Server Components (Default)     - Initial page data
2. Data Access Layer               - Auth-verified data access
3. TanStack React Query            - Client-side caching & revalidation
4. Server Actions                  - Mutations and form submissions
```

---

## Server-Side Data Fetching (Preferred)

### With Data Access Layer

```tsx
// lib/dal/projects.ts
import { auth } from '@/auth'
import { cache } from 'react'

export const verifyAuth = cache(async () => {
  const session = await auth()
  if (!session?.user) throw new Error('Unauthorized')
  return session
})

export async function getProjects() {
  const session = await verifyAuth() // ALWAYS verify auth
  return db.projects.findMany({
    where: { userId: session.user.id },
    orderBy: { createdAt: 'desc' },
  })
}

export async function getProject(id: string) {
  const session = await verifyAuth()
  return db.projects.findFirst({
    where: { id, userId: session.user.id },
  })
}
```

### In Server Components

```tsx
// app/projects/page.tsx
import { getProjects } from '@/lib/dal/projects'
import { Suspense } from 'react'
import { ProjectListSkeleton } from '@/components/skeletons'

export default async function ProjectsPage() {
  return (
    <div>
      <h1>Projects</h1>
      <Suspense fallback={<ProjectListSkeleton />}>
        <ProjectList />
      </Suspense>
    </div>
  )
}

async function ProjectList() {
  const projects = await getProjects()
  return (
    <ul>
      {projects.map(project => (
        <li key={project.id}>{project.name}</li>
      ))}
    </ul>
  )
}
```

---

## Client-Side with TanStack React Query

### Configuration

```tsx
// app/providers.tsx
'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { useState } from 'react'

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 5 * 60 * 1000,      // 5 minutes
        gcTime: 10 * 60 * 1000,        // 10 minutes (formerly cacheTime)
        refetchOnWindowFocus: false,
        retry: (failureCount, error) => {
          if (error instanceof Response && error.status === 401) return false
          return failureCount < 3
        },
      },
      mutations: {
        retry: false,
      },
    },
  }))

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {process.env.NODE_ENV === 'development' && <ReactQueryDevtools />}
    </QueryClientProvider>
  )
}
```

### Custom Hooks

```tsx
// hooks/useProjects.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getProjects, createProject, deleteProject } from '@/services/api/projects'

export function useProjects() {
  return useQuery({
    queryKey: ['projects'],
    queryFn: getProjects,
    staleTime: 5 * 60 * 1000,
  })
}

export function useProject(id: string) {
  return useQuery({
    queryKey: ['projects', id],
    queryFn: () => getProject(id),
    enabled: !!id,
  })
}

export function useCreateProject() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: createProject,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}

export function useDeleteProject() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: deleteProject,
    onMutate: async (projectId) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['projects'] })

      // Snapshot previous value
      const previousProjects = queryClient.getQueryData(['projects'])

      // Optimistically remove from cache
      queryClient.setQueryData(['projects'], (old: Project[]) =>
        old?.filter(p => p.id !== projectId)
      )

      return { previousProjects }
    },
    onError: (err, projectId, context) => {
      // Rollback on error
      queryClient.setQueryData(['projects'], context?.previousProjects)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}
```

### Query Key Conventions

```ts
// Query key patterns
['projects']                    // List all projects
['projects', projectId]         // Single project
['projects', { status: 'active' }]  // Filtered list
['users', userId, 'projects']   // User's projects

// Invalidation patterns
queryClient.invalidateQueries({ queryKey: ['projects'] })  // All project queries
queryClient.invalidateQueries({ queryKey: ['projects', id] })  // Single project
```

---

## Server Actions for Mutations

Prefer Server Actions over API routes for mutations:

```tsx
// app/actions/projects.ts
'use server'

import { auth } from '@/auth'
import { revalidatePath, revalidateTag } from 'next/cache'

export async function createProject(formData: FormData) {
  const session = await auth({ ensureSignedIn: true })

  const project = await db.projects.create({
    data: {
      name: formData.get('name') as string,
      userId: session.user.id,
    },
  })

  revalidatePath('/projects')
  revalidateTag('projects')

  return { success: true, project }
}

export async function deleteProject(id: string) {
  const session = await auth({ ensureSignedIn: true })

  await db.projects.delete({
    where: { id, userId: session.user.id },
  })

  revalidatePath('/projects')
  return { success: true }
}
```

---

## Caching Strategies

### Time-Based Revalidation

```tsx
// app/projects/page.tsx
export const revalidate = 60 // Revalidate every 60 seconds
```

### On-Demand Revalidation

```tsx
import { revalidatePath, revalidateTag } from 'next/cache'

// Revalidate by path
revalidatePath('/projects')

// Revalidate by tag
revalidateTag('projects')
```

### Upcoming: 'use cache' Directive

```tsx
// Future pattern (Next.js 15.3+)
async function getData() {
  'use cache'
  return fetch('https://api.example.com/data')
}
```

---

## Loading States

### With Suspense

```tsx
// app/projects/page.tsx
import { Suspense } from 'react'

export default function ProjectsPage() {
  return (
    <Suspense fallback={<ProjectListSkeleton />}>
      <ProjectList />
    </Suspense>
  )
}
```

### With loading.tsx

```tsx
// app/projects/loading.tsx
export default function Loading() {
  return <ProjectListSkeleton />
}
```

### With React Query

```tsx
function ProjectList() {
  const { data, isLoading, error } = useProjects()

  if (isLoading) return <ProjectListSkeleton />
  if (error) return <ErrorMessage error={error} />

  return (
    <ul>
      {data?.map(project => (
        <li key={project.id}>{project.name}</li>
      ))}
    </ul>
  )
}
```

---

## Error Handling

```tsx
// components/ErrorBoundary.tsx
'use client'

import { useQueryErrorResetBoundary } from '@tanstack/react-query'
import { ErrorBoundary } from 'react-error-boundary'

export function QueryErrorBoundary({ children }: { children: React.ReactNode }) {
  const { reset } = useQueryErrorResetBoundary()

  return (
    <ErrorBoundary
      onReset={reset}
      fallbackRender={({ error, resetErrorBoundary }) => (
        <div>
          <h2>Something went wrong</h2>
          <p>{error.message}</p>
          <Button onClick={resetErrorBoundary}>Try again</Button>
        </div>
      )}
    >
      {children}
    </ErrorBoundary>
  )
}
```

---

## API Client Pattern

```tsx
// services/api/client.ts
import { auth } from '@/auth'

export async function apiClient<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const session = await auth()

  const response = await fetch(`${process.env.API_URL}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(session?.accessToken && {
        Authorization: `Bearer ${session.accessToken}`,
      }),
      ...options.headers,
    },
  })

  if (!response.ok) {
    throw new Error(`API Error: ${response.status}`)
  }

  return response.json()
}

// services/api/projects.ts
import { apiClient } from './client'

export const getProjects = () => apiClient<Project[]>('/projects')
export const getProject = (id: string) => apiClient<Project>(`/projects/${id}`)
export const createProject = (data: CreateProjectInput) =>
  apiClient<Project>('/projects', {
    method: 'POST',
    body: JSON.stringify(data),
  })
```

---

## Examples

<example>
✅ Server Component with DAL
```tsx
// app/dashboard/page.tsx
import { getDashboardData } from '@/lib/dal/dashboard'

export default async function DashboardPage() {
  const data = await getDashboardData() // Auth verified in DAL
  return <Dashboard data={data} />
}
```
</example>

<example>
✅ Client-side with React Query
```tsx
'use client'
import { useProjects, useDeleteProject } from '@/hooks/useProjects'

export function ProjectList() {
  const { data: projects, isLoading } = useProjects()
  const deleteMutation = useDeleteProject()

  if (isLoading) return <Skeleton />

  return (
    <ul>
      {projects?.map(p => (
        <li key={p.id}>
          {p.name}
          <Button onClick={() => deleteMutation.mutate(p.id)}>Delete</Button>
        </li>
      ))}
    </ul>
  )
}
```
</example>

<example type="invalid">
❌ Fetching in useEffect (Avoid)
```tsx
'use client'
export function ProjectList() {
  const [projects, setProjects] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/projects')
      .then(r => r.json())
      .then(setProjects)
      .finally(() => setLoading(false))
  }, [])

  // Use Server Components or React Query instead!
}
```
</example>

---

## Anti-Patterns

- ❌ Using SWR (use TanStack React Query instead)
- ❌ Fetching in `useEffect`
- ❌ Fetching without auth verification (use DAL)
- ❌ API routes for mutations (use Server Actions)
- ❌ No loading states or error handling
- ❌ Hardcoded API URLs in components
- ❌ Not using query key conventions
