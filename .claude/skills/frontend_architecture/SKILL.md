---
description: Frontend architecture overview for Alpha Tales. Reference this when understanding the codebase structure, making architectural decisions, or onboarding new developers.
globs:
alwaysApply: false
---

# Frontend Architecture Overview

## Critical Rules

- If this is applied, please add a comment to the top of the page "Frontend architecture rule applied"
- **Framework**: Next.js 15 with App Router (file-based routing)
- **React Version**: React 19 with automatic compiler optimizations
- **Feature-Based Architecture**: Organize code by feature, not by type
- **Server Components by Default**: Only use `"use client"` when interactivity is required
- **Data Access Layer**: Verify authentication at every data access point
- **State Separation**: Zustand for client state, TanStack React Query for server state
- **Package Manager**: pnpm (critical requirement - do not use npm or yarn)

---

## Technology Stack

| Concern | Technology | Version |
|---------|------------|---------|
| Framework | Next.js (App Router) | 15.1.6 → 15.2.3+ |
| React | React 19 | 19.0.0 |
| Language | TypeScript | 5.4.5 (strict mode) |
| UI Components | Shadcn/UI | Latest |
| Styling | Tailwind CSS | 3.4.1 |
| Client State | Zustand | 5.0.3 |
| Server State | TanStack React Query | 5.83.0 |
| Forms | React Hook Form + Zod | 7.55.0 / 3.25.76 |
| Authentication | WorkOS AuthKit | Latest |
| Observability | Datadog RUM + PostHog | Latest |
| Testing | Vitest + Playwright | Latest |
| Real-time | Socket.IO | Latest |
| Package Manager | pnpm | 9.1.0 |

---

## Directory Structure

```
frontend/alphatales-web/
├── app/                          # Next.js 15 App Router
│   ├── (app)/                   # Route group: authenticated pages with sidebar
│   │   ├── account/
│   │   ├── billing/
│   │   ├── projects/
│   │   ├── settings/
│   │   ├── team-management/
│   │   └── layout.tsx           # Shared layout with sidebar
│   ├── (no-sidebar)/            # Route group: pages without sidebar
│   ├── api/                      # API routes (edge functions)
│   │   ├── auth/                # Auth endpoints
│   │   ├── billing/             # Stripe endpoints
│   │   └── agent/               # AI agent endpoints
│   ├── auth/                     # Public auth pages
│   ├── project/[projectId]/     # Dynamic project routes
│   ├── layout.tsx               # Root layout
│   ├── providers.tsx            # Provider composition
│   └── globals.css              # Design tokens & global styles
│
├── features/                     # Feature modules (self-contained)
│   ├── auth/                     # Authentication feature
│   │   ├── components/          # Feature-specific UI
│   │   ├── hooks/               # Feature-specific hooks
│   │   ├── services/            # Feature-specific API
│   │   ├── types/               # Feature-specific types
│   │   └── utils/               # Feature-specific utilities
│   ├── projects/                 # Projects management
│   │   ├── components/
│   │   │   ├── wizard/          # Project creation wizard
│   │   │   ├── list/            # Project listing
│   │   │   └── loading/         # Loading skeletons
│   │   ├── context/             # Feature context
│   │   ├── hooks/
│   │   ├── services/
│   │   ├── types/
│   │   ├── utils/
│   │   └── validation/          # Zod schemas
│   ├── profile/
│   ├── feedback/
│   └── team-management/
│
├── components/                   # Shared components
│   ├── ui/                       # Shadcn/UI base components
│   ├── common/                   # Generic reusable components
│   ├── composite/                # Multi-component compositions
│   ├── layouts/                  # Layout wrappers
│   ├── forms/                    # Form components
│   ├── dialogs/                  # Modal/dialog components
│   ├── error-boundaries/         # Error boundary implementations
│   └── features/                 # Feature-specific shared UI
│
├── store/                        # Zustand global state stores
│   ├── authStore.ts             # User authentication state
│   ├── projectStore.ts          # Project cache and state
│   ├── userStoryStore.ts        # User stories state
│   ├── featureStore.ts          # Feature flags
│   ├── themeStore.ts            # Theme preference
│   └── inviteDialogStore.ts     # UI state
│
├── hooks/                        # Global custom hooks
│   ├── useAuthenticatedApi.ts   # API calls with auth
│   ├── useProjectData.ts        # Project data fetching
│   ├── useConnectivity.ts       # Online/offline detection
│   ├── useErrorHandler.ts       # Error handling logic
│   └── useValidationSocket.ts   # Real-time validation
│
├── services/                     # Business logic & API
│   ├── api/                      # API service layer
│   │   ├── auth.ts
│   │   ├── project.ts
│   │   ├── teams.ts
│   │   └── billing.ts
│   ├── infrastructure/           # Infrastructure services
│   │   ├── logger.ts
│   │   ├── error-handler.ts
│   │   ├── rate-limiter.ts
│   │   ├── resilience.ts
│   │   └── socket.ts
│   ├── http.ts                   # Axios HTTP client (central)
│   └── endpoints.ts              # API endpoint URLs
│
├── lib/                          # Utilities and helpers
│   ├── authkit/                  # WorkOS AuthKit
│   │   ├── client.tsx           # Client-side auth
│   │   └── next-auth-react.ts
│   ├── observability/            # Telemetry (45+ files)
│   │   ├── client.ts            # Browser telemetry
│   │   ├── ai-metrics.ts        # AI performance tracking
│   │   ├── error-handling.ts    # Error tracking
│   │   ├── circuit-breaker.ts   # Failure protection
│   │   └── ...
│   ├── utils.ts                  # cn() and utilities
│   └── design-tokens.ts          # Theme tokens
│
├── types/                        # TypeScript definitions
│   ├── api.ts                    # API types
│   ├── project.ts                # Domain types
│   └── socket-events.ts          # WebSocket types
│
├── schemas/                      # Zod validation schemas
├── constants/                    # App constants
├── utils/                        # Utility functions
├── context/                      # React Context
├── providers/                    # Provider components
├── styles/                       # Global styles
├── public/                       # Static assets
├── __tests__/                    # Unit tests
├── e2e/                          # Playwright E2E tests
│
├── auth.ts                       # Server-side auth helper
├── middleware.ts                 # Route protection
├── instrumentation.ts            # OpenTelemetry setup
├── next.config.js                # Next.js config
├── tailwind.config.ts            # Tailwind config
└── tsconfig.json                 # TypeScript config
```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                        PRESENTATION LAYER                        │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │    │
│  │  │ App Router   │  │ Server       │  │ Client Components    │   │    │
│  │  │ (Pages)      │  │ Components   │  │ ("use client")       │   │    │
│  │  └──────────────┘  └──────────────┘  └──────────────────────┘   │    │
│  │                                                                  │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │    │
│  │  │ Shadcn/UI    │  │ Feature      │  │ Layout Components    │   │    │
│  │  │ Components   │  │ Components   │  │                      │   │    │
│  │  └──────────────┘  └──────────────┘  └──────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                    │                                     │
│                                    ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                         STATE LAYER                              │    │
│  │  ┌────────────────────────┐  ┌────────────────────────────┐     │    │
│  │  │   Zustand Stores       │  │   TanStack React Query     │     │    │
│  │  │   (Client State)       │  │   (Server State)           │     │    │
│  │  │  ─────────────────     │  │  ─────────────────────     │     │    │
│  │  │  • authStore           │  │  • Query caching           │     │    │
│  │  │  • projectStore        │  │  • Automatic refetching    │     │    │
│  │  │  • themeStore          │  │  • Optimistic updates      │     │    │
│  │  │  • uiStore             │  │  • Background sync         │     │    │
│  │  └────────────────────────┘  └────────────────────────────┘     │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                    │                                     │
│                                    ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                      DATA ACCESS LAYER                           │    │
│  │  ┌────────────────────────┐  ┌────────────────────────────┐     │    │
│  │  │   Server Actions       │  │   API Services             │     │    │
│  │  │   ("use server")       │  │   (services/api/)          │     │    │
│  │  │  ─────────────────     │  │  ─────────────────────     │     │    │
│  │  │  • Form mutations      │  │  • HTTP client (Axios)     │     │    │
│  │  │  • Auth verification   │  │  • Error handling          │     │    │
│  │  │  • Cache invalidation  │  │  • Token injection         │     │    │
│  │  └────────────────────────┘  └────────────────────────────┘     │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                    │                                     │
│                                    ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                     INFRASTRUCTURE LAYER                         │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │    │
│  │  │ WorkOS       │  │ Datadog RUM  │  │ WebSocket            │   │    │
│  │  │ AuthKit      │  │ + PostHog    │  │ (Socket.IO)          │   │    │
│  │  └──────────────┘  └──────────────┘  └──────────────────────┘   │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │    │
│  │  │ Error        │  │ Circuit      │  │ Rate Limiting        │   │    │
│  │  │ Boundaries   │  │ Breaker      │  │                      │   │    │
│  │  └──────────────┘  └──────────────┘  └──────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                        ┌──────────────────────┐
                        │   Backend API        │
                        │   (Go Services)      │
                        └──────────────────────┘
```

---

## Feature-Based Architecture

Each feature is self-contained with its own components, hooks, services, and types:

```
features/[feature-name]/
├── components/        # Feature-specific UI components
├── hooks/            # Feature-specific custom hooks
├── services/         # Feature-specific API services
├── types/            # Feature-specific type definitions
├── utils/            # Feature-specific utilities
├── validation/       # Feature-specific Zod schemas
├── context/          # Feature-specific React context (if needed)
└── index.ts          # Barrel exports
```

### Example: Projects Feature

```
features/projects/
├── components/
│   ├── wizard/
│   │   ├── ProjectWizard.tsx
│   │   ├── StepOne.tsx
│   │   └── StepTwo.tsx
│   ├── list/
│   │   ├── ProjectList.tsx
│   │   └── ProjectCard.tsx
│   └── loading/
│       └── ProjectSkeleton.tsx
├── hooks/
│   ├── useProjectCreation.ts
│   └── useProjectActions.ts
├── context/
│   └── ProjectCreationContext.tsx
├── types/
│   └── project.types.ts
├── validation/
│   └── project.schema.ts
└── index.ts
```

---

## Routing Architecture

### Route Groups

```
app/
├── (app)/                    # Authenticated routes with sidebar
│   ├── projects/page.tsx     # /projects
│   ├── settings/page.tsx     # /settings
│   ├── account/page.tsx      # /account
│   └── layout.tsx            # Sidebar layout
│
├── (no-sidebar)/             # Authenticated routes without sidebar
│   └── checkout/page.tsx     # /checkout
│
├── auth/                     # Public auth routes
│   ├── login/page.tsx        # /auth/login
│   ├── signup/page.tsx       # /auth/signup
│   └── verify-account/[token]/page.tsx
│
├── project/[projectId]/      # Dynamic project routes
│   ├── page.tsx              # /project/:id
│   └── [tab]/page.tsx        # /project/:id/:tab
│
└── api/                      # API routes
    ├── auth/
    ├── billing/
    └── webhooks/
```

### Route Protection

```
┌──────────────────────────────────────────────────────────────┐
│                      middleware.ts                            │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  1. Cookie reassembly (WorkOS session chunking)        │  │
│  │  2. Public path check (bypass auth for public routes)  │  │
│  │  3. WorkOS AuthKit middleware (session validation)     │  │
│  │  4. Redirect unauthenticated users to /auth/login      │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                  Data Access Layer (DAL)                      │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  ALWAYS verify auth at data access (defense-in-depth)  │  │
│  │  Never rely solely on middleware (CVE-2025-29927)      │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## State Management Architecture

### Client State (Zustand)

```typescript
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
        partialize: (state) => ({ user: state.user }),
      }
    )
  )
)

// Memoized selectors
export const useUser = () => useAuthStore((state) => state.user)
export const useIsAuthenticated = () => useAuthStore((state) => state.isAuthenticated)
```

### Server State (TanStack React Query)

```typescript
// hooks/useProjects.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

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
    staleTime: 5 * 60 * 1000,
  })
}

export function useDeleteProject() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: deleteProject,
    onMutate: async (projectId) => {
      await queryClient.cancelQueries({ queryKey: projectKeys.all })
      const previous = queryClient.getQueryData(projectKeys.lists())
      queryClient.setQueryData(projectKeys.lists(), (old: Project[]) =>
        old?.filter((p) => p.id !== projectId)
      )
      return { previous }
    },
    onError: (err, projectId, context) => {
      queryClient.setQueryData(projectKeys.lists(), context?.previous)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: projectKeys.all })
    },
  })
}
```

---

## Provider Hierarchy

```tsx
// app/providers.tsx
export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ErrorBoundary fallback={<GlobalErrorFallback />}>
      <AuthSessionProvider>
        <QueryClientProvider client={queryClient}>
          <ThemeProvider attribute="class" defaultTheme="system">
            <LogoutConfirmProvider>
              <ModalProvider>
                <ProjectCreationProvider>
                  <Toaster />
                  <SonnerToaster />
                  {children}
                </ProjectCreationProvider>
              </ModalProvider>
            </LogoutConfirmProvider>
          </ThemeProvider>
          {process.env.NODE_ENV === 'development' && <ReactQueryDevtools />}
        </QueryClientProvider>
      </AuthSessionProvider>
    </ErrorBoundary>
  )
}
```

---

## Authentication Architecture

### WorkOS AuthKit Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Browser   │────▶│  Middleware │────▶│  WorkOS     │
│             │     │  (Next.js)  │     │  AuthKit    │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │
       │                   │                   │
       ▼                   ▼                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Session    │     │  Cookie     │     │  JWT        │
│  Provider   │◀────│  Reassembly │◀────│  Token      │
│  (Client)   │     │  (>4KB)     │     │             │
└─────────────┘     └─────────────┘     └─────────────┘
```

### Authentication Methods

- **OAuth** - Google, GitHub, Microsoft
- **Magic Link** - Email-based passwordless
- **Password** - Traditional email/password
- **MFA** - Multi-factor authentication
- **SAML/SSO** - Enterprise SSO

### Session Management

```typescript
// Server-side (auth.ts)
import { auth } from '@/auth'

export async function getServerSession() {
  const session = await auth()
  if (!session?.user) throw new Error('Unauthorized')
  return session
}

// Client-side (lib/authkit/client.tsx)
import { useAuth, useAccessToken } from '@/lib/authkit/client'

export function useCurrentUser() {
  const { user, isAuthenticated } = useAuth()
  return { user, isAuthenticated }
}
```

---

## Data Fetching Patterns

### Server Components (Default)

```tsx
// app/projects/page.tsx - Server Component
import { getProjects } from '@/lib/dal/projects'

export default async function ProjectsPage() {
  const projects = await getProjects() // Auth verified in DAL
  return <ProjectList projects={projects} />
}
```

### Client-Side with React Query

```tsx
// components/ProjectList.tsx
'use client'

import { useProjects } from '@/hooks/useProjects'

export function ProjectList() {
  const { data: projects, isLoading, error } = useProjects()

  if (isLoading) return <ProjectSkeleton />
  if (error) return <ErrorMessage error={error} />

  return (
    <ul>
      {projects?.map((project) => (
        <ProjectCard key={project.id} project={project} />
      ))}
    </ul>
  )
}
```

### Server Actions for Mutations

```typescript
// app/actions/projects.ts
'use server'

import { auth } from '@/auth'
import { revalidatePath } from 'next/cache'

export async function createProject(prevState: ActionState, formData: FormData) {
  const session = await auth({ ensureSignedIn: true })

  const validated = projectSchema.safeParse(Object.fromEntries(formData))
  if (!validated.success) {
    return { error: validated.error.errors[0].message }
  }

  await db.projects.create({
    data: { ...validated.data, userId: session.user.id },
  })

  revalidatePath('/projects')
  return { success: true }
}
```

---

## Observability Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        OBSERVABILITY                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────┐  ┌─────────────────────┐               │
│  │  Server-Side        │  │  Client-Side        │               │
│  │  ────────────────   │  │  ────────────────   │               │
│  │  • OpenTelemetry    │  │  • Datadog RUM      │               │
│  │  • Vercel OTEL      │  │  • Datadog Logs     │               │
│  │  • OTLP Export      │  │  • PostHog          │               │
│  └─────────────────────┘  └─────────────────────┘               │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Shared Features                       │    │
│  │  • Correlation IDs (distributed tracing)                 │    │
│  │  • Error tracking with categorization                    │    │
│  │  • AI metrics (token usage, latency, cost)              │    │
│  │  • Circuit breaker pattern                               │    │
│  │  • Cardinality protection                                │    │
│  │  • Budget controls                                       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Error Handling Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│                     ERROR BOUNDARIES                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Global Error Boundary (Root Layout)                     │    │
│  │  └─▶ Catches unhandled errors                           │    │
│  │  └─▶ Reports to Datadog                                 │    │
│  │  └─▶ Shows fallback UI                                  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                         │                                        │
│                         ▼                                        │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Session Error Boundary                                  │    │
│  │  └─▶ Catches auth errors                                │    │
│  │  └─▶ Redirects to login                                 │    │
│  └─────────────────────────────────────────────────────────┘    │
│                         │                                        │
│                         ▼                                        │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Component Error Boundaries                              │    │
│  │  └─▶ Isolates component failures                        │    │
│  │  └─▶ Shows component-specific fallback                  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                         │                                        │
│                         ▼                                        │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  React Query Error Handling                              │    │
│  │  └─▶ Mutation rollback                                  │    │
│  │  └─▶ Toast notifications                                │    │
│  │  └─▶ Retry logic                                        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Performance Patterns

### React 19 Compiler

```tsx
// React 19 compiler handles memoization automatically
// AVOID excessive manual optimization

// ❌ Before (unnecessary)
const filteredItems = useMemo(() => items.filter(i => i.active), [items])
const handleClick = useCallback(() => onClick(id), [onClick, id])

// ✅ After (let compiler handle it)
const filteredItems = items.filter(i => i.active)
const handleClick = () => onClick(id)
```

### Code Splitting

```tsx
import dynamic from 'next/dynamic'

const HeavyChart = dynamic(() => import('@/components/HeavyChart'), {
  loading: () => <ChartSkeleton />,
})
```

### Streaming with Suspense

```tsx
// app/projects/page.tsx
import { Suspense } from 'react'

export default function ProjectsPage() {
  return (
    <div>
      <h1>Projects</h1>
      <Suspense fallback={<ProjectListSkeleton />}>
        <ProjectList />
      </Suspense>
    </div>
  )
}
```

---

## Testing Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      TESTING PYRAMID                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│                         ┌───────┐                                │
│                        /   E2E   \                               │
│                       /  Playwright \                            │
│                      /───────────────\                           │
│                     /                  \                         │
│                    /   Integration      \                        │
│                   /    React Testing     \                       │
│                  /       Library          \                      │
│                 /──────────────────────────\                     │
│                /                            \                    │
│               /        Unit Tests            \                   │
│              /         Vitest                 \                  │
│             /──────────────────────────────────\                 │
│                                                                  │
│  Tools:                                                          │
│  • Vitest - Unit tests                                          │
│  • React Testing Library - Component tests                       │
│  • Playwright - End-to-end tests                                │
│  • jest-axe - Accessibility testing                             │
│  • MSW - API mocking                                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Build & Deployment

### Build Configuration

```javascript
// next.config.js
module.exports = {
  output: 'standalone', // Docker-optimized build
  experimental: {
    instrumentationHook: true, // OpenTelemetry
  },
}
```

### Environment Variables

```bash
# .env.local
NEXT_PUBLIC_API_URL=http://localhost:8080
NEXT_PUBLIC_POSTHOG_KEY=phc_xxx
NEXT_PUBLIC_POSTHOG_HOST=https://app.posthog.com
WORKOS_API_KEY=sk_xxx
WORKOS_CLIENT_ID=client_xxx
NEXT_PUBLIC_WORKOS_REDIRECT_URI=http://localhost:3000/auth/callback
DATADOG_API_KEY=xxx
DATADOG_APPLICATION_ID=xxx
DATADOG_CLIENT_TOKEN=xxx
```

### Scripts

```json
{
  "scripts": {
    "dev": "next dev --turbo",
    "build": "next build",
    "start": "next start",
    "test": "vitest",
    "test:e2e": "playwright test",
    "lint": "biome check ."
  }
}
```

---

## Examples

<example>
✅ Correct Architecture Pattern
```
features/
├── projects/
│   ├── components/
│   │   ├── ProjectList.tsx      # Server Component
│   │   └── ProjectForm.tsx      # Client Component ("use client")
│   ├── hooks/
│   │   └── useProjectActions.ts # Feature-specific hook
│   ├── services/
│   │   └── project.api.ts       # API calls
│   ├── types/
│   │   └── project.types.ts     # TypeScript types
│   └── index.ts                 # Barrel exports

store/
├── projectStore.ts              # Client state (Zustand)

hooks/
├── useProjectsQuery.ts          # Server state (React Query)

app/
├── (app)/
│   └── projects/
│       └── page.tsx             # Route page
```
</example>

<example type="invalid">
❌ Incorrect Architecture Pattern
```
// Everything dumped in components/
components/
├── ProjectList.tsx
├── ProjectForm.tsx
├── projectApi.ts               # API in components!
├── projectTypes.ts             # Types in components!
├── useProjectHook.ts           # Hook in components!
└── projectStore.ts             # Store in components!

// No feature organization
// No separation of concerns
// Hard to maintain and scale
```
</example>

---

## Anti-Patterns

- ❌ Mixing API calls, state, and UI in same component
- ❌ Using `"use client"` on components without interactivity
- ❌ Relying only on middleware for authentication (use DAL)
- ❌ Fetching data in `useEffect` instead of Server Components/React Query
- ❌ Manual `useMemo`/`useCallback` without profiler evidence
- ❌ Putting feature-specific code in shared directories
- ❌ Using npm or yarn instead of pnpm
- ❌ Hardcoded API URLs in components
- ❌ Business logic in Client Components
