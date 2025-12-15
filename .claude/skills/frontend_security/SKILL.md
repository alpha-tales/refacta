---
description: Security hardening standards for Alpha Tales' Next 15 frontend. Apply to every route, component, and API handler to prevent XSS, CSRF, credential-stuffing, click-jacking, token leakage and supply-chain risk.
globs:
alwaysApply: false
---

# Front-End Security Standards

## Critical Rules

- If this is applied, please add a comment to the top of the page "Frontend security rule applied"
- **CRITICAL: Data Access Layer** - Authentication MUST be verified at every data access point, NOT just middleware (defense-in-depth against CVE-2025-29927).
- **Framework patch level** - Lock Next.js to **>= 15.2.3** (fix for middleware-bypass CVE-2025-29927). **Current version 15.1.6 is VULNERABLE - upgrade required.**
- **Block x-middleware-subrequest** - Configure WAF/proxy to block requests with `x-middleware-subrequest` header.
- **Content-Security-Policy** - Use per-request nonce with directives: `default-src 'self'; script-src 'self' 'nonce-{nonce}'; object-src 'none'; base-uri 'self'; frame-src 'none'; form-action 'self'; upgrade-insecure-requests;`
- **Cross-origin isolation** - Send `Cross-Origin-Opener-Policy: same-origin` and `Cross-Origin-Embedder-Policy: require-corp` headers.
- **Permissions-Policy** - Deny powerful APIs (`camera=(), microphone=(), geolocation=()`) via header.
- **Strict cookie strategy** - Session cookies: `HttpOnly; Secure; SameSite=Lax`. No tokens in `localStorage` or query-string.
- **Rate-limit sensitive endpoints** - Use rate limiting (10 req/IP/min) for login, signup, password reset.
- **Input validation** - All API routes & forms must validate via **Zod** before hitting business logic.
- **ESLint hardening** - `eslint-plugin-security` plus `no-dangerously-set-inner-html` rule enforced.
- **Secret hygiene** - `.env*` must be git-ignored; enable **GitHub push-protection** to block secrets.
- **Source-map stripping** - Keep `productionBrowserSourceMaps: false` to avoid leaking code paths.
- **Log security events** - Use structured logger (see 200-logging-observability) to emit auth failures with `route`, `ip`, `user_id`, `trace_id` to Datadog.

---

## CRITICAL: Data Access Layer Pattern (2025 Best Practice)

**CVE-2025-29927 demonstrated that middleware alone is NOT sufficient for authentication.**

### Defense-in-Depth Strategy

```
Request Flow:
┌─────────────────────────────────────────────────────────────┐
│  1. WAF/Proxy        Block x-middleware-subrequest header   │
├─────────────────────────────────────────────────────────────┤
│  2. Middleware       First line of defense (can be bypassed)│
├─────────────────────────────────────────────────────────────┤
│  3. Data Access Layer   ALWAYS verify auth (REQUIRED)       │
├─────────────────────────────────────────────────────────────┤
│  4. Database         Row-level security (recommended)       │
└─────────────────────────────────────────────────────────────┘
```

### Implementation Pattern

```ts
// lib/dal/index.ts - Data Access Layer
import { auth } from '@/auth'
import { cache } from 'react'

// Cache auth check per request to avoid multiple DB calls
export const verifyAuth = cache(async () => {
  const session = await auth()
  if (!session?.user) {
    throw new Error('Unauthorized')
  }
  return session
})

// lib/dal/projects.ts
import { verifyAuth } from './index'

export async function getProjects() {
  const session = await verifyAuth() // ALWAYS verify at DAL
  return db.projects.findMany({
    where: { userId: session.user.id }
  })
}

export async function getProject(id: string) {
  const session = await verifyAuth() // ALWAYS verify at DAL
  return db.projects.findFirst({
    where: { id, userId: session.user.id }
  })
}

export async function createProject(data: ProjectInput) {
  const session = await verifyAuth() // ALWAYS verify at DAL
  return db.projects.create({
    data: { ...data, userId: session.user.id }
  })
}
```

### Why This Matters

- **CVE-2025-29927**: Attackers bypassed middleware by spoofing `x-middleware-subrequest` header
- **Server Components**: Can access data without going through middleware
- **Route Handlers**: May be called directly, bypassing middleware
- **EVERY data access point MUST independently verify authentication**

---

## CVE-2025-29927: Middleware Authorization Bypass

### Vulnerability Details

- **CVE ID**: CVE-2025-29927
- **CVSS Score**: 9.1 (Critical)
- **Disclosure Date**: March 21, 2025
- **Affected Versions**: Next.js < 12.3.5, < 13.5.9, < 14.2.25, < 15.2.3

### How the Attack Works

```
Attacker sends:
GET /protected-page HTTP/1.1
Host: target.com
x-middleware-subrequest: 1    <-- Bypasses middleware entirely

Result: Middleware never executes, authentication skipped
```

### Mitigations

1. **Upgrade Next.js** to >= 15.2.3 (primary fix)
2. **Block header at WAF/proxy level**:
```nginx
# Nginx
if ($http_x_middleware_subrequest) {
    return 403;
}
```
3. **Implement Data Access Layer** (defense-in-depth)
4. **Add regression test**:
```ts
test('middleware not bypassed with forged header', async ({ request }) => {
  const res = await request.get('/projects', {
    headers: { 'x-middleware-subrequest': '1' },
  })
  expect(res.status()).toBe(401)
})
```

---

## Header Implementation (next.config.js)

```js
module.exports = {
  async headers() {
    return [{
      source: '/(.*)',
      headers: [
        {
          key: 'Content-Security-Policy',
          value: "default-src 'self'; script-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'; upgrade-insecure-requests;",
        },
        {
          key: 'Cross-Origin-Opener-Policy',
          value: 'same-origin',
        },
        {
          key: 'Cross-Origin-Embedder-Policy',
          value: 'require-corp',
        },
        {
          key: 'Permissions-Policy',
          value: 'camera=(), microphone=(), geolocation=()',
        },
        {
          key: 'Strict-Transport-Security',
          value: 'max-age=63072000; includeSubDomains; preload',
        },
        {
          key: 'Referrer-Policy',
          value: 'strict-origin-when-cross-origin',
        },
        {
          key: 'X-Content-Type-Options',
          value: 'nosniff',
        },
        {
          key: 'X-Frame-Options',
          value: 'DENY',
        },
      ],
    }]
  },
  productionBrowserSourceMaps: false,
}
```

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
  const { success, limit, remaining, reset } = await authLimiter.limit(ip)

  if (!success) {
    return new Response('Too Many Requests', {
      status: 429,
      headers: {
        'X-RateLimit-Limit': limit.toString(),
        'X-RateLimit-Remaining': remaining.toString(),
        'X-RateLimit-Reset': reset.toString(),
      },
    })
  }

  // Process request...
}
```

---

## Input Validation with Zod

```ts
import { z } from 'zod'

// Define schemas
const loginSchema = z.object({
  email: z.string().email('Invalid email'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
})

const projectSchema = z.object({
  name: z.string().min(1).max(100),
  description: z.string().max(1000).optional(),
})

// API route usage
export async function POST(request: Request) {
  const body = await request.json()

  // Validate input - throws on invalid
  const validated = loginSchema.safeParse(body)

  if (!validated.success) {
    return Response.json(
      { error: 'Validation failed', details: validated.error.flatten() },
      { status: 400 }
    )
  }

  // Safe to use validated.data
  const { email, password } = validated.data
}
```

---

## Cookie Security (WorkOS)

WorkOS AuthKit manages cookies automatically with secure defaults:

| Cookie | Attributes |
|--------|------------|
| `wos-session` | HttpOnly, Secure, SameSite=Lax |
| `wos-session.0`, `.1` | Chunked cookies for large sessions |
| `user-account-info` | App-managed, not HttpOnly |

**Rules:**
- Never store tokens in `localStorage` or `sessionStorage`
- Never pass tokens in URL query strings
- Never manually create or modify `wos-session` cookies

---

## Security Logging

```ts
import { authLogger } from '@/lib/observability/logger'

// Log authentication failure
authLogger.warn({
  event: 'auth_failure',
  reason: 'invalid_credentials',
  email: redactEmail(email),
  ip: request.headers.get('x-forwarded-for'),
  userAgent: request.headers.get('user-agent'),
}, 'Authentication failed')

// Log rate limit hit
authLogger.warn({
  event: 'rate_limit_exceeded',
  route: '/api/auth/login',
  ip: request.headers.get('x-forwarded-for'),
  limit: 10,
  window: '1m',
}, 'Rate limit exceeded')

// Log suspicious activity
authLogger.error({
  event: 'security_alert',
  type: 'middleware_bypass_attempt',
  header: 'x-middleware-subrequest',
  ip: request.headers.get('x-forwarded-for'),
}, 'Potential middleware bypass attempt detected')
```

---

## CSP Violation Monitoring

Send CSP violations to Datadog:

```ts
// Report-To header configuration
{
  key: 'Report-To',
  value: JSON.stringify({
    group: 'csp-violations',
    max_age: 86400,
    endpoints: [{ url: '/api/csp-report' }],
  }),
}

// API route to receive violations
// app/api/csp-report/route.ts
export async function POST(request: Request) {
  const violation = await request.json()

  authLogger.warn({
    event: 'csp_violation',
    directive: violation['violated-directive'],
    blockedUri: violation['blocked-uri'],
    documentUri: violation['document-uri'],
  }, 'CSP violation detected')

  return new Response(null, { status: 204 })
}
```

---

## Middleware Bypass Regression Test

```ts
// e2e/security.spec.ts
import { test, expect } from '@playwright/test'

test.describe('Security: Middleware Bypass Prevention', () => {
  test('blocks x-middleware-subrequest header on protected routes', async ({ request }) => {
    const res = await request.get('/projects', {
      headers: { 'x-middleware-subrequest': '1' },
    })
    expect(res.status()).toBe(401)
  })

  test('blocks x-middleware-subrequest header on auth callback', async ({ request }) => {
    const res = await request.post('/api/auth/callback', {
      headers: { 'x-middleware-subrequest': '1' },
      form: { code: 'malicious' },
    })
    expect(res.status()).toBe(401)
  })

  test('blocks x-middleware-subrequest header on API routes', async ({ request }) => {
    const res = await request.get('/api/v1/projects', {
      headers: { 'x-middleware-subrequest': '1' },
    })
    expect(res.status()).toBe(401)
  })
})
```

---

## Environment Security Checklist

- [ ] `.env*` files in `.gitignore`
- [ ] GitHub push protection enabled for secrets
- [ ] `NODE_ENV=production` set in production
- [ ] `productionBrowserSourceMaps: false` in next.config.js
- [ ] Security headers configured (CSP, HSTS, etc.)
- [ ] Rate limiting on auth endpoints
- [ ] Zod validation on all inputs
- [ ] Data Access Layer implemented
- [ ] Next.js >= 15.2.3 (CVE-2025-29927 fix)
- [ ] Regression tests for middleware bypass
- [ ] Security logging to Datadog
- [ ] WAF blocking x-middleware-subrequest header

---

## Anti-Patterns

<example type="invalid">
- Relying solely on middleware for authentication (CVE-2025-29927)
- Using Next.js < 15.2.3 without WAF protection
- Not implementing Data Access Layer verification
- Storing tokens in localStorage or sessionStorage
- Inline scripts without nonce (CSP violation)
- Login endpoint without rate limiting
- API routes without Zod validation
- Committing .env files to git
- Enabling source maps in production
- Not logging security events
- Trusting x-middleware-subrequest header
</example>
