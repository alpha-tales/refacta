---
description: Authentication & session standards for Alpha Tales (Next.js 15 + WorkOS AuthKit). Load this rule when working on /api/auth routes, login/refresh logic, middleware, or any code that consumes the session.
globs:
alwaysApply: false
---

# Auth-Standards (WorkOS AuthKit)

## Critical Rules

- If this is applied, please add a comment to the top of the page "Auth standards rule applied"
- **Framework patch** - Pin **Next.js >= 15.2.3** to include the fix for CVE-2025-29927 (middleware bypass). Current version 15.1.6 is VULNERABLE.
- **Auth provider** - Use **WorkOS AuthKit** (`@workos-inc/authkit-nextjs`) for authentication - NOT Auth.js/NextAuth.
- **Data Access Layer** - Authentication MUST be verified at every data access point, not just middleware. See Security Standards (210) for DAL pattern.
- **Cookie model** - WorkOS manages session cookies automatically via `wos-session` cookie (HttpOnly, Secure, SameSite=Lax).
- **Large sessions** - WorkOS chunks cookies > 4096 bytes automatically (`wos-session.0`, `wos-session.1`, etc.).
- **No tokens in localStorage** - All tokens stored in encrypted HttpOnly cookies only.
- **Rate-limit sensitive routes** - Wrap `/api/auth/*` with rate limiting (10 req/IP/min) to block brute-force.
- **Validation layer** - All credential or magic-link providers must parse input with **Zod** before processing.
- **Logging & tracing** - Emit auth events to Datadog RUM and log failures with Pino for correlation.
- **Middleware guards** - Protect pages via `authkitMiddleware()`; add Playwright test that forges `x-middleware-subrequest: 1` and expects 401.

---

## Environment Variables

```env
# WorkOS Configuration
WORKOS_API_KEY=sk_...                    # WorkOS API key
WORKOS_CLIENT_ID=client_...              # WorkOS client ID
WORKOS_REDIRECT_URI=https://app.example.com/api/auth/callback
WORKOS_COOKIE_NAME=wos-session           # Session cookie name (default: wos-session)
WORKOS_COOKIE_MAX_AGE=2592000            # 30 days in seconds
```

---

## Server-Side Session Access (`/auth.ts`)

```ts
import { getTokenClaims, withAuth } from '@workos-inc/authkit-nextjs'
import type { JWTPayload } from 'jose'

interface Claims extends JWTPayload {
  sid?: string
  org_id?: string
  role?: string
  roles?: string[]
  permissions?: string[]
  entitlements?: string[]
  feature_flags?: string[]
}

export interface ServerSession {
  user: AuthenticatedUser
  accessToken?: string
  organizationId?: string
  role?: string
  roles?: string[]
  permissions?: string[]
  entitlements?: string[]
  featureFlags?: string[]
  impersonator?: { email: string; reason: string | null }
  expires?: string
  expiresAt?: number
}

export async function auth(options?: { ensureSignedIn?: boolean }): Promise<ServerSession | null> {
  const sessionInfo = await withAuth({ ensureSignedIn: options?.ensureSignedIn ?? false })

  if (!sessionInfo.user) {
    return null
  }

  const claims = await getTokenClaims<Claims>(sessionInfo.accessToken)
  const { expires, expiresAt } = computeExpiry(claims)

  return {
    user: buildUser(sessionInfo.user),
    accessToken: sessionInfo.accessToken,
    organizationId: sessionInfo.organizationId,
    role: sessionInfo.role,
    roles: sessionInfo.roles,
    permissions: sessionInfo.permissions,
    entitlements: sessionInfo.entitlements,
    featureFlags: sessionInfo.featureFlags,
    impersonator: sessionInfo.impersonator,
    expires,
    expiresAt,
  }
}
```

---

## Middleware Configuration (`/middleware.ts`)

```ts
import { authkitMiddleware } from '@workos-inc/authkit-nextjs'
import { NextRequest, NextResponse } from 'next/server'

const PUBLIC_PATHS = [
  '/',
  '/login',
  '/signup',
  '/auth/login',
  '/auth/signup',
  '/auth/error',
  '/api/auth/login',
  '/api/auth/callback',
  '/api/auth/session',
  '/api/health',
  '/privacy',
  '/terms',
]

const workosMiddleware = authkitMiddleware({
  debug: process.env.NODE_ENV !== 'production',
  redirectUri: process.env.WORKOS_REDIRECT_URI,
  middlewareAuth: {
    enabled: true,
    unauthenticatedPaths: PUBLIC_PATHS,
  },
})

export default async function middleware(request: NextRequest) {
  // Reassemble chunked cookies if present (for large session cookies)
  const processedRequest = reassembleChunkedCookies(request)

  // Check if public path
  const isPublicPath = PUBLIC_PATHS.some(path =>
    request.nextUrl.pathname === path || request.nextUrl.pathname.startsWith(path)
  )

  if (isPublicPath) {
    return await workosMiddleware(processedRequest)
  }

  // For protected paths, validate session
  const cookieName = process.env.WORKOS_COOKIE_NAME || 'wos-session'
  const sessionCookie = processedRequest.cookies.get(cookieName)

  if (!sessionCookie) {
    return NextResponse.redirect(new URL('/auth/login', request.url))
  }

  return await workosMiddleware(processedRequest)
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|images|public).*)'],
}
```

---

## Client-Side Components (`/lib/authkit/client.tsx`)

### AuthSessionProvider

```tsx
'use client'

import { AuthKitProvider } from '@workos-inc/authkit-nextjs/components'
import type { ReactNode } from 'react'

export function AuthSessionProvider({
  children,
  onSessionExpired,
}: {
  children: ReactNode
  onSessionExpired?: (() => void) | false
}) {
  return <AuthKitProvider onSessionExpired={onSessionExpired}>{children}</AuthKitProvider>
}
```

### useSession Hook

```tsx
'use client'

import { useAuth, useAccessToken } from '@workos-inc/authkit-nextjs/components'
import { useMemo, useCallback } from 'react'

export type SessionStatus = 'loading' | 'authenticated' | 'unauthenticated'

export function useSession() {
  const auth = useAuth()
  const { accessToken, loading: tokenLoading, error: tokenError, refresh } = useAccessToken()

  const status: SessionStatus =
    auth.loading || tokenLoading ? 'loading' : auth.user ? 'authenticated' : 'unauthenticated'

  const session = useMemo(() => {
    if (!auth.user) return null
    return {
      user: mapUser(auth.user),
      accessToken,
      organizationId: auth.organizationId,
      role: auth.role,
      roles: auth.roles,
      permissions: auth.permissions,
      entitlements: auth.entitlements,
      featureFlags: auth.featureFlags,
      impersonator: auth.impersonator,
    }
  }, [auth, accessToken])

  const update = useCallback(async () => {
    try {
      await auth.refreshAuth({ ensureSignedIn: false })
      await refresh()
    } catch (error) {
      console.warn('[useSession] Token refresh failed:', error)
    }
  }, [auth, refresh])

  return { data: session, status, update, error: tokenError }
}
```

### signIn / signOut Functions

```tsx
export async function signIn(
  _provider?: string,
  options: { callbackUrl?: string; redirect?: boolean; loginHint?: string } = {}
) {
  const search = new URLSearchParams()
  if (options.callbackUrl) search.set('callbackUrl', options.callbackUrl)
  if (options.loginHint) search.set('loginHint', options.loginHint)

  const target = `/api/auth/login${search.size > 0 ? `?${search.toString()}` : ''}`

  if (options.redirect === false) {
    return { ok: true, status: 200, url: target }
  }

  window.location.assign(target)
  return { ok: true, status: 200, url: target }
}

export async function signOut(options: { redirect?: boolean; callbackUrl?: string } = {}) {
  const response = await fetch('/api/auth/logout', {
    method: 'POST',
    credentials: 'include',
  })

  const body = await response.json().catch(() => ({}))
  const logoutUrl = body.logoutUrl || options.callbackUrl || '/auth/login'

  if (options.redirect !== false) {
    window.location.assign(logoutUrl)
  }

  return { ok: response.ok, status: response.status, url: logoutUrl }
}
```

---

## Root Layout Integration

```tsx
// app/layout.tsx
import { AuthSessionProvider } from '@/lib/authkit/client'

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthSessionProvider onSessionExpired={() => window.location.assign('/auth/login')}>
          {children}
        </AuthSessionProvider>
      </body>
    </html>
  )
}
```

---

## Data Access Layer Integration (CRITICAL)

**Middleware is NOT sufficient for authentication. Always verify at data access points:**

```ts
// lib/dal/users.ts
import { auth } from '@/auth'

export async function getUserProfile() {
  const session = await auth({ ensureSignedIn: true })
  // Session verified at DAL level - safe to proceed
  return fetchProfile(session.user.id)
}

// lib/dal/projects.ts
export async function getProjects() {
  const session = await auth({ ensureSignedIn: true })
  return db.projects.findMany({ where: { userId: session.user.id } })
}
```

---

## Organization/Team Support

WorkOS handles organization membership automatically:

```ts
// Access organization info from session
const session = await auth()
const { organizationId, role, roles, permissions } = session

// Check permissions
if (!permissions?.includes('projects:write')) {
  throw new Error('Insufficient permissions')
}

// Check role
if (role !== 'admin' && !roles?.includes('admin')) {
  throw new Error('Admin access required')
}
```

---

## MFA Support

WorkOS AuthKit supports MFA enrollment and verification:

| Route | Purpose |
|-------|---------|
| `/auth/mfa-enroll` | MFA enrollment page |
| `/auth/mfa-verify` | MFA verification page |
| `/api/auth/mfa/enroll` | MFA enrollment API |
| `/api/auth/mfa/challenge` | MFA challenge API |
| `/api/auth/mfa/verify` | MFA verification API |
| `/api/auth/mfa/disable` | MFA disable API |

---

## Cookie Security

WorkOS manages cookie security automatically:

| Cookie | Attributes |
|--------|------------|
| `wos-session` | HttpOnly, Secure, SameSite=Lax, Path=/ |
| `wos-session.0`, `.1`, etc. | Chunked cookies for large sessions |
| `wos-session.chunks` | Chunk count indicator |

**Never manually set or modify WorkOS session cookies.**

---

## Rate Limiting

```ts
// lib/rate-limit.ts
import { Ratelimit } from '@upstash/ratelimit'
import { Redis } from '@upstash/redis'

export const authLimiter = new Ratelimit({
  redis: Redis.fromEnv(),
  limiter: Ratelimit.slidingWindow(10, '1 m'), // 10 requests per minute
  analytics: true,
})

// Usage in API route
export async function POST(request: Request) {
  const ip = request.headers.get('x-forwarded-for') ?? 'anonymous'
  const { success, limit, remaining } = await authLimiter.limit(ip)

  if (!success) {
    return new Response('Too Many Requests', { status: 429 })
  }

  // Process login...
}
```

---

## Zod Validation for Auth Inputs

```ts
import { z } from 'zod'

const loginSchema = z.object({
  email: z.string().email('Invalid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
})

const magicLinkSchema = z.object({
  email: z.string().email('Invalid email address'),
})

// Usage
export async function POST(request: Request) {
  const body = await request.json()
  const validated = loginSchema.parse(body) // Throws on invalid
  // Process with validated.email, validated.password
}
```

---

## Middleware Bypass Regression Test (Playwright)

```ts
import { test, expect } from '@playwright/test'

test('middleware not bypassed with forged header', async ({ request }) => {
  const res = await request.get('/projects', {
    headers: { 'x-middleware-subrequest': '1' },
  })
  expect(res.status()).toBe(401) // Should still be blocked
})

test('middleware not bypassed on callback', async ({ request }) => {
  const res = await request.post('/api/auth/callback', {
    headers: { 'x-middleware-subrequest': '1' },
    form: { code: 'evil' },
  })
  expect(res.status()).toBe(401)
})
```

---

## Session Monitoring Component

```tsx
// components/auth/SessionMonitor.tsx
'use client'

import { useSession } from '@/lib/authkit/client'
import { useEffect, useRef } from 'react'

export function SessionMonitor() {
  const { data: session, status, update } = useSession()
  const intervalRef = useRef<NodeJS.Timeout>()

  useEffect(() => {
    // Refresh session every 5 minutes
    intervalRef.current = setInterval(() => {
      if (status === 'authenticated') {
        update()
      }
    }, 5 * 60 * 1000)

    return () => clearInterval(intervalRef.current)
  }, [status, update])

  useEffect(() => {
    // Check session expiry
    if (session?.expiresAt && Date.now() > session.expiresAt) {
      window.location.assign('/auth/login')
    }
  }, [session?.expiresAt])

  return null
}
```

---

## Anti-Patterns

<example type="invalid">
- Using Auth.js/NextAuth instead of WorkOS AuthKit (wrong provider)
- Relying solely on middleware for authentication (CVE-2025-29927)
- Storing tokens in localStorage or sessionStorage
- Not validating inputs with Zod before auth processing
- Manually manipulating WorkOS session cookies
- Not implementing rate limiting on auth endpoints
- Skipping Data Access Layer authentication verification
- Using Next.js < 15.2.3 (vulnerable to middleware bypass)
</example>

---

## File Reference

| File | Purpose |
|------|---------|
| `/auth.ts` | Server-side session access with `auth()` function |
| `/middleware.ts` | WorkOS middleware configuration |
| `/lib/authkit/client.tsx` | Client-side auth components and hooks |
| `/components/auth/SessionMonitor.tsx` | Session monitoring component |
| `/components/auth/SessionErrorBoundary.tsx` | Auth error boundary |
| `/components/auth/LogoutCleanup.tsx` | Logout cleanup handler |
| `/app/api/auth/login/route.ts` | Login API route |
| `/app/api/auth/logout/route.ts` | Logout API route |
| `/app/api/auth/callback/route.ts` | OAuth callback handler |
| `/app/api/auth/session/route.ts` | Session info API |
