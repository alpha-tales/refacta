---
description: Standards for authoring feature-scoped React hooks in Alpha Tales. Apply when creating or refactoring hooks to encapsulate domain logic cleanly and predictably.
globs:
alwaysApply: false
---

# Feature-Hooks Standards

## Critical Rules

- If this is applied, please add a comment to the top of the page "Feature hooks rule applied"
- Create **one hooks file per feature** (`<feature>/hooks.ts`); export public hooks via the feature's `index.ts`.
- All hooks must start with **`use`** and follow single-responsibility naming (`useCartTotals` not `cartHook`).
- Expose `{data, error, isLoading, ...actions}` objects; never return positional tuples.
- Internally manage **feature state** (Zustand, Context) and **server state** (React Query) but never mix concerns in the component layer.
- Implement optimistic mutations with rollback; surface errors via a shared toaster/boundary.
- **React 19 Compiler** handles memoization automatically—avoid excessive `useMemo`/`useCallback` unless profiler confirms need.
- Write a **unit test** per hook covering happy path, error path, and side-effects; reset stores/query-client between tests.

---

## React 19 Compiler Optimization

React 19's compiler automatically optimizes component re-renders and handles memoization:

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
- Zustand selectors (always use selectors for store subscriptions)

---

## Folder & File Layout

```
src/
└─ features/
   └─ orders/
      ├─ hooks.ts          # feature hooks
      ├─ components/…
      ├─ api/…
      └─ index.ts          # re-exports
```

Central, reusable helpers live in `src/shared/hooks/`.

---

## Hook Design Patterns

| Concern | Guidance |
|---------|----------|
| **Naming** | `use + Verb/Noun` (e.g. `useOrderDetails`) |
| **Return shape** | Object with named keys for clarity & DX |
| **State separation** | UI state → `useState`/Zustand; server state → React Query |
| **Caching / Revalidation** | Delegate to React Query's `staleTime`, `refetchOnWindowFocus` |
| **Optimistic updates** | `onMutate / onError / onSettled` pattern |
| **Error handling** | Standardise via `useErrorBoundary` or toast helper |
| **Testing** | Mock fetchers, wrap in `QueryClientProvider`, reset between specs |

---

## Shared vs Feature Hooks

- **Shared** (`shared/hooks/`): generic helpers like `useDebounce`, `useInterval`.
- **Feature** (`features/cart/hooks.ts`): domain logic (`useCartTotals`, `useAddToCart`).
- A feature hook may **compose** shared hooks but never the reverse.

---

## Query Keys Factory Pattern

```ts
// features/projects/queryKeys.ts
export const projectKeys = {
  all: ['projects'] as const,
  lists: () => [...projectKeys.all, 'list'] as const,
  list: (filters: ProjectFilters) => [...projectKeys.lists(), filters] as const,
  details: () => [...projectKeys.all, 'detail'] as const,
  detail: (id: string) => [...projectKeys.details(), id] as const,
}
```

---

## Example – Feature Hook with React Query

```ts
// features/orders/hooks.ts
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getOrder, updateOrder, deleteOrder } from './api'
import { toast } from '@/shared/ui/toast'

// Query keys factory
export const orderKeys = {
  all: ['orders'] as const,
  detail: (id: string) => [...orderKeys.all, id] as const,
}

export function useOrderDetails(orderId: string) {
  return useQuery({
    queryKey: orderKeys.detail(orderId),
    queryFn: () => getOrder(orderId),
    staleTime: 5 * 60 * 1000,
    enabled: !!orderId,
  })
}

export function useUpdateOrder() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: updateOrder,
    onMutate: async (newData) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: orderKeys.detail(newData.id) })

      // Snapshot previous value
      const previous = queryClient.getQueryData(orderKeys.detail(newData.id))

      // Optimistically update
      queryClient.setQueryData(orderKeys.detail(newData.id), (old) => ({
        ...old,
        ...newData,
      }))

      return { previous }
    },
    onError: (err, newData, context) => {
      // Rollback on error
      if (context?.previous) {
        queryClient.setQueryData(orderKeys.detail(newData.id), context.previous)
      }
      toast.error('Save failed')
    },
    onSettled: (data, err, newData) => {
      queryClient.invalidateQueries({ queryKey: orderKeys.detail(newData.id) })
    },
  })
}
```

---

## Example – Server Action Integration

```ts
// features/projects/hooks.ts
import { useActionState } from 'react'
import { useOptimistic, useTransition } from 'react'
import { createProject, deleteProject } from '@/app/actions/projects'

// For forms using Server Actions
export function useCreateProjectForm() {
  const [state, formAction] = useActionState(createProject, null)
  return { state, formAction }
}

// For optimistic updates with Server Actions
export function useProjectsOptimistic(projects: Project[]) {
  const [optimisticProjects, addOptimistic] = useOptimistic(
    projects,
    (state, newProject: Project) => [...state, { ...newProject, pending: true }]
  )
  const [isPending, startTransition] = useTransition()

  const addProject = async (formData: FormData) => {
    const newProject = {
      id: crypto.randomUUID(),
      name: formData.get('name') as string,
    }
    startTransition(() => addOptimistic(newProject))
    await createProject(null, formData)
  }

  return { optimisticProjects, addProject, isPending }
}
```

---

## Zustand Store Hooks

```ts
// features/cart/hooks.ts
import { useCartStore } from '@/store/cartStore'

// Use selectors to prevent unnecessary re-renders
export const useCartItems = () => useCartStore((state) => state.items)
export const useCartTotal = () => useCartStore((state) => state.total)
export const useCartActions = () => useCartStore((state) => ({
  addItem: state.addItem,
  removeItem: state.removeItem,
  clearCart: state.clearCart,
}))
```

---

## Testing Pattern

```ts
// features/orders/hooks.test.ts
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useOrderDetails } from './hooks'
import { getOrder } from './api'

vi.mock('./api')

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return ({ children }) => (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  )
}

describe('useOrderDetails', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('returns order data on success', async () => {
    const mockOrder = { id: '123', status: 'pending' }
    vi.mocked(getOrder).mockResolvedValue(mockOrder)

    const { result } = renderHook(() => useOrderDetails('123'), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(mockOrder)
  })

  it('handles error state', async () => {
    vi.mocked(getOrder).mockRejectedValue(new Error('Failed'))

    const { result } = renderHook(() => useOrderDetails('123'), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})
```

---

## Examples

<example>
✅ Correct Pattern
```ts
// Good: named return object, proper separation
export function useOrderDetails(orderId: string) {
  const { data, error, isLoading } = useQuery({
    queryKey: ['orders', orderId],
    queryFn: () => getOrder(orderId),
    enabled: !!orderId,
  })

  const updateMutation = useMutation({
    mutationFn: updateOrder,
    onError: () => toast.error('Save failed'),
  })

  // No manual memoization needed - React Compiler handles it
  const formattedTotal = data ? formatCurrency(data.total) : null

  return { order: data, error, isLoading, update: updateMutation.mutate, formattedTotal }
}
```
</example>

<example type="invalid">
❌ Incorrect Pattern
```ts
// BAD: tuple return, mixed concerns, excessive memoization
export function userHook() {
  const [open, setOpen] = useState(false)           // UI state
  const { data } = useQuery({ queryKey: ['users'] }) // server data

  // Unnecessary with React 19 Compiler
  const filtered = useMemo(() => data?.filter(u => u.active), [data])
  const toggle = useCallback(() => setOpen(o => !o), [])

  return [open, setOpen, data, filtered]            // tuple - unclear
}
```
</example>

---

## Anti-Patterns

- ❌ Returning positional tuples instead of named objects
- ❌ Mixing UI state and server state in same hook without clear separation
- ❌ Excessive `useMemo`/`useCallback` without profiler evidence
- ❌ Not using query key factories for React Query
- ❌ Missing optimistic update patterns for mutations
- ❌ Not resetting stores/query-client between tests
- ❌ Feature hooks depending on shared hooks (not the reverse)
