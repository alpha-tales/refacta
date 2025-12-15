---
description: Standards for managing client (Zustand) and server (TanStack React Query) state in Alpha Tales. Apply when adding or refactoring state logic to ensure scalability, performance, and UX consistency.
globs:
alwaysApply: false
---

# State-Management Standards

## Critical Rules

- If this is applied, please add a comment to the top of the page "State management rule applied"
- **Client vs Server**: Use **Zustand** (5.0.3) for client/UI state; use **TanStack React Query** (5.83.0) for server data. Never mix the two.
- **Store Scope**: Create feature-scoped stores (or slices) in `store/` to avoid a monolithic store.
- **Typed State**: All state, actions and selectors MUST be fully typed with TypeScript.
- **Selectors & Memoization**: Export memoized selectors to prevent needless re-renders.
- **React Compiler**: Let React 19 compiler handle memoization - avoid manual `useMemo`/`useCallback`.
- **Server Actions**: Use for mutations instead of API routes.
- **Optimistic Updates**: Implement with React Query's `onMutate`/`onError`/`onSettled` pattern.
- **DevTools**: Enable Zustand + React Query DevTools in development only.

---

## Library Versions & Responsibilities

| Concern | Tool | Version | Notes |
|---------|------|---------|-------|
| UI / auth / wizard state | **Zustand** | 5.0.3 | Split into feature stores |
| Server data & mutations | **TanStack React Query** | 5.83.0 | Caching, background refetch |
| Form state | **React Hook Form** | 7.55.0 | Complex forms only |
| Theme / locale | **React Context** | - | Lightweight cross-tree |

---

## Zustand Store Organization

### Feature-Scoped Stores

```ts
// store/authStore.ts
import { create } from 'zustand'
import { persist, subscribeWithSelector } from 'zustand/middleware'

interface AuthState {
  user: User | null
  isAuthenticated: boolean
  setUser: (user: User | null) => void
  clearUser: () => void
}

export const useAuthStore = create<AuthState>()(
  subscribeWithSelector(
    persist(
      (set) => ({
        user: null,
        isAuthenticated: false,
        setUser: (user) => set({ user, isAuthenticated: !!user }),
        clearUser: () => set({ user: null, isAuthenticated: false }),
      }),
      {
        name: 'auth-storage',
        partialize: (state) => ({ user: state.user }), // Only persist user
      }
    )
  )
)

// Memoized selector
export const useUser = () => useAuthStore((state) => state.user)
export const useIsAuthenticated = () => useAuthStore((state) => state.isAuthenticated)
```

```ts
// store/projectStore.ts
import { create } from 'zustand'

interface ProjectState {
  currentProject: Project | null
  projects: Project[]
  setCurrentProject: (project: Project | null) => void
  setProjects: (projects: Project[]) => void
  addOptimisticProject: (project: Project) => void
  removeOptimisticProject: (id: string) => void
}

export const useProjectStore = create<ProjectState>((set) => ({
  currentProject: null,
  projects: [],
  setCurrentProject: (project) => set({ currentProject: project }),
  setProjects: (projects) => set({ projects }),
  addOptimisticProject: (project) =>
    set((state) => ({ projects: [...state.projects, project] })),
  removeOptimisticProject: (id) =>
    set((state) => ({ projects: state.projects.filter((p) => p.id !== id) })),
}))
```

### Store Directory Structure

```
store/
├── authStore.ts          # Authentication state
├── projectStore.ts       # Project management state
├── themeStore.ts         # Theme preferences
├── uiStore.ts            # UI state (modals, sidebars)
└── index.ts              # Barrel exports
```

---

## TanStack React Query Configuration

### QueryClient Setup

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
        gcTime: 10 * 60 * 1000,        // 10 minutes
        refetchOnWindowFocus: false,
        retry: (failureCount, error) => {
          // Don't retry on 401/403
          if (error instanceof Response && [401, 403].includes(error.status)) {
            return false
          }
          return failureCount < 3
        },
        retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
      },
      mutations: {
        retry: false,
      },
    },
  }))

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {process.env.NODE_ENV === 'development' && (
        <ReactQueryDevtools initialIsOpen={false} />
      )}
    </QueryClientProvider>
  )
}
```

### Query Hooks Pattern

```ts
// hooks/useProjects.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

// Query keys factory
export const projectKeys = {
  all: ['projects'] as const,
  lists: () => [...projectKeys.all, 'list'] as const,
  list: (filters: ProjectFilters) => [...projectKeys.lists(), filters] as const,
  details: () => [...projectKeys.all, 'detail'] as const,
  detail: (id: string) => [...projectKeys.details(), id] as const,
}

export function useProjects(filters?: ProjectFilters) {
  return useQuery({
    queryKey: projectKeys.list(filters ?? {}),
    queryFn: () => fetchProjects(filters),
  })
}

export function useProject(id: string) {
  return useQuery({
    queryKey: projectKeys.detail(id),
    queryFn: () => fetchProject(id),
    enabled: !!id,
  })
}
```

---

## Optimistic Updates Pattern

```ts
// hooks/useDeleteProject.ts
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { deleteProject } from '@/app/actions/projects'
import { projectKeys } from './useProjects'

export function useDeleteProject() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: deleteProject,
    onMutate: async (projectId: string) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: projectKeys.all })

      // Snapshot previous value
      const previousProjects = queryClient.getQueryData(projectKeys.lists())

      // Optimistically update
      queryClient.setQueryData(projectKeys.lists(), (old: Project[] | undefined) =>
        old?.filter((p) => p.id !== projectId)
      )

      return { previousProjects }
    },
    onError: (err, projectId, context) => {
      // Rollback on error
      if (context?.previousProjects) {
        queryClient.setQueryData(projectKeys.lists(), context.previousProjects)
      }
    },
    onSettled: () => {
      // Always refetch after error or success
      queryClient.invalidateQueries({ queryKey: projectKeys.all })
    },
  })
}
```

---

## Zustand + React Query Integration

```tsx
// Sync server data to Zustand for derived state
function ProjectProvider({ children }: { children: React.ReactNode }) {
  const { data: projects } = useProjects()
  const setProjects = useProjectStore((state) => state.setProjects)

  useEffect(() => {
    if (projects) {
      setProjects(projects)
    }
  }, [projects, setProjects])

  return <>{children}</>
}
```

---

## React 19 Compiler Notes

React 19's compiler automatically handles memoization. Avoid:

```tsx
// BEFORE (unnecessary with React 19 Compiler)
const filteredProjects = useMemo(
  () => projects.filter((p) => p.status === 'active'),
  [projects]
)

const handleClick = useCallback(() => onClick(id), [onClick, id])

// AFTER (let compiler handle it)
const filteredProjects = projects.filter((p) => p.status === 'active')
const handleClick = () => onClick(id)
```

**When to still use manual memoization:**
- React DevTools Profiler confirms performance issue
- Complex calculations (> 16ms)
- Callbacks passed to non-React libraries

---

## Testing Helpers

```ts
// test/helpers/state.ts
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useAuthStore } from '@/store/authStore'

// Reset stores between tests
export function resetStores() {
  useAuthStore.setState({ user: null, isAuthenticated: false })
  useProjectStore.setState({ currentProject: null, projects: [] })
}

// Create fresh QueryClient per test
export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
}

// Test wrapper
export function createWrapper() {
  const queryClient = createTestQueryClient()
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  )
}
```

---

## Examples

<example>
✅ Correct Pattern
```tsx
// Feature-scoped store
// store/cartStore.ts
export const useCartStore = create<CartState>((set) => ({
  items: [],
  addItem: (item) => set((s) => ({ items: [...s.items, item] })),
}))

// React Query for server data
// hooks/useProducts.ts
export const useProducts = () => useQuery({
  queryKey: ['products'],
  queryFn: fetchProducts,
  staleTime: 10 * 60 * 1000,
})

// Optimistic mutation
const addToCartMutation = useMutation({
  mutationFn: addToCart,
  onMutate: optimisticAdd,
  onError: rollback,
})
```
</example>

<example type="invalid">
❌ Incorrect Pattern
```tsx
// Giant monolithic store
const useGlobalStore = create((set) => ({
  user: null,
  cart: [],
  products: [],
  orders: [],
  // Everything in one store!
}))

// Fetching in useEffect without caching
useEffect(() => {
  fetch('/api/products').then(r => r.json()).then(setProducts)
}, [])

// No error handling or loading states
```
</example>

---

## Anti-Patterns

- ❌ Monolithic store with all state
- ❌ Mixing Zustand and React Query for same data
- ❌ Fetching in `useEffect` without caching
- ❌ Manual `useMemo`/`useCallback` without profiler evidence
- ❌ No optimistic updates for mutations
- ❌ DevTools enabled in production
- ❌ Untyped state and actions
