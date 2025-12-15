---
description: Standards for logging, tracing, and observability in Alpha Tales with Datadog RUM, PostHog, and OpenTelemetry. Apply when adding or refactoring any telemetry, logging, or monitoring code.
globs:
alwaysApply: false
---

# Logging & Observability Standards (Datadog + PostHog + OpenTelemetry)

## Critical Rules

- If this is applied, please add a comment to the top of the page "Logging observability rule applied"
- **Enable Next.js instrumentation hook** via `instrumentation.ts` and register `@vercel/otel` for server-side tracing.
- **Client-side monitoring** - Use **Datadog RUM** (`@datadog/browser-rum`) for Real User Monitoring and session replay.
- **Client-side logs** - Use **Datadog Logs** (`@datadog/browser-logs`) for structured client logging.
- **Product analytics** - Use **PostHog** (`posthog-js`) for feature flags and product analytics.
- **Server-side tracing** - Use **@vercel/otel** for OpenTelemetry integration.
- **Structured logging** - Use the custom logger with correlation IDs (`trace_id`, `span_id`, `correlation_id`).
- **PII redaction** - Always redact sensitive fields (`password`, `token`, `cookie`, `authorization`, `secret`).
- **Log sampling** - Apply sampling to prevent log explosion in production.

---

## Technology Stack

| Concern | Tool | Package | Version |
|---------|------|---------|---------|
| Client RUM | Datadog RUM | @datadog/browser-rum | ^5.25.0 |
| Client Logs | Datadog Logs | @datadog/browser-logs | ^5.25.0 |
| Product Analytics | PostHog | posthog-js | ^1.157.2 |
| Server Tracing | Vercel OTEL | @vercel/otel | ^1.8.3 |
| OpenTelemetry API | OTEL API | @opentelemetry/api | ^1.9.0 |
| Vercel Analytics | Vercel | @vercel/analytics | ^1.5.0 |

---

## Environment Variables

```env
# Datadog Configuration
NEXT_PUBLIC_DD_APPLICATION_ID=xxx      # Datadog RUM application ID
NEXT_PUBLIC_DD_CLIENT_TOKEN=xxx        # Datadog client token
NEXT_PUBLIC_DD_SITE=datadoghq.com      # Datadog site (default: datadoghq.com)
NEXT_PUBLIC_DD_ENV=dev                 # Environment tag (dev/staging/prod)
NEXT_PUBLIC_DD_SERVICE=alphatales-web  # Service name
NEXT_PUBLIC_DD_VERSION=1.0.0           # Application version

# Sampling Configuration
NEXT_PUBLIC_DD_SESSION_SAMPLE_RATE=100         # RUM session sample rate (0-100)
NEXT_PUBLIC_DD_SESSION_REPLAY_SAMPLE_RATE=0    # Session replay sample rate (0-100)
NEXT_PUBLIC_DD_LOG_LEVEL=info                  # Log level (debug/info/warn/error)

# Feature Flags
NEXT_PUBLIC_DD_TRACK_USER_INTERACTIONS=true
NEXT_PUBLIC_DD_TRACK_RESOURCES=true
NEXT_PUBLIC_DD_TRACK_LONG_TASKS=true

# PostHog Configuration
NEXT_PUBLIC_POSTHOG_KEY=phc_xxx        # PostHog project API key
NEXT_PUBLIC_POSTHOG_HOST=https://app.posthog.com

# Application
NEXT_PUBLIC_APP_VERSION=1.0.0          # Application version for tagging
```

---

## Project File Structure

| File | Purpose |
|------|---------|
| `instrumentation.ts` | Next.js instrumentation hook, registers `@vercel/otel` |
| `lib/observability/index.ts` | Main exports for observability module |
| `lib/observability/setup.ts` | Observability system initialization |
| `lib/observability/client.ts` | Client-side Datadog initialization |
| `lib/observability/logger.ts` | Structured logging with sampling |
| `lib/observability/datadog-utils.ts` | Datadog tag resolution utilities |
| `lib/observability/correlation.ts` | Correlation ID management |
| `lib/observability/webVitals.ts` | Core Web Vitals reporting |
| `lib/observability/metrics.ts` | Custom metrics collection |
| `lib/observability/log-sampling.ts` | Log sampling configuration |
| `lib/observability/errorBoundary.tsx` | React error boundary with logging |

---

## Server-Side Instrumentation (`instrumentation.ts`)

```ts
import { registerOTel } from '@vercel/otel'

export async function register() {
  try {
    // Register Vercel OpenTelemetry first
    registerOTel('alphatales-web')

    // Then initialize custom observability system
    const { setupObservability } = await import('./lib/observability')

    setupObservability({
      serviceName: 'alphatales-web',
      serviceVersion: process.env.NEXT_PUBLIC_APP_VERSION || '1.0.0',
      environment: process.env.NODE_ENV || 'development',
    })

    console.log('Server-side observability initialized successfully')
  } catch (error) {
    console.error('Failed to initialize server-side observability:', error)
  }
}
```

---

## Client-Side Datadog Initialization

```ts
// lib/observability/client.ts
'use client'

async function initializeDatadogTelemetry(config: TelemetryBootstrapConfig) {
  if (typeof window === 'undefined') return

  const applicationId = process.env.NEXT_PUBLIC_DD_APPLICATION_ID
  const clientToken = process.env.NEXT_PUBLIC_DD_CLIENT_TOKEN

  if (!applicationId || !clientToken) {
    console.debug('Datadog telemetry disabled - missing credentials')
    return
  }

  const [{ datadogRum }, { datadogLogs }] = await Promise.all([
    import('@datadog/browser-rum'),
    import('@datadog/browser-logs'),
  ])

  datadogRum.init({
    applicationId,
    clientToken,
    site: process.env.NEXT_PUBLIC_DD_SITE || 'datadoghq.com',
    service: config.serviceName,
    env: config.environment,
    version: config.serviceVersion,
    sessionSampleRate: 100,
    sessionReplaySampleRate: 0,
    trackUserInteractions: true,
    trackResources: true,
    trackLongTasks: true,
    defaultPrivacyLevel: 'mask-user-input',
    silentMultipleInit: true,
  })

  datadogLogs.init({
    clientToken,
    site: process.env.NEXT_PUBLIC_DD_SITE || 'datadoghq.com',
    forwardErrorsToLogs: true,
    forwardConsoleLogs: ['error'],
    sampleRate: 100,
    service: config.serviceName,
    env: config.environment,
    version: config.serviceVersion,
    silentMultipleInit: true,
  })
}
```

---

## Structured Logging

### Logger Usage

```ts
import { logger, apiLogger, authLogger, errorLogger } from '@/lib/observability/logger'

// Basic logging
logger.info({ action: 'user_login', userId: '123' }, 'User logged in')
logger.warn({ component: 'ProjectForm', issue: 'validation_failed' }, 'Form validation failed')
logger.error({ error: err, context: 'API call' }, 'API request failed')

// Specialized loggers
apiLogger.debug({ url: '/api/projects', method: 'GET' }, 'API Request')
authLogger.info({ event: 'login_success' }, 'User authenticated')
errorLogger.error({ error: err, component: 'Dashboard' }, 'Unhandled error')
```

### Available Specialized Loggers

| Logger | Module | Use Case |
|--------|--------|----------|
| `logger` | general | Default logger |
| `apiLogger` | api | API requests/responses |
| `authLogger` | auth | Authentication events |
| `errorLogger` | error | Error tracking |
| `perfLogger` | performance | Performance metrics |
| `userJourneyLogger` | user_journey | User actions/navigation |
| `uiLogger` | ui | UI component events |

### Logging Functions

```ts
import {
  logApiRequest,
  logApiResponse,
  logError,
  logUserAction,
  logPageView,
  logPerformance,
} from '@/lib/observability/logger'

// Log API request
logApiRequest({ url: '/api/projects', method: 'POST', requestId: 'req-123' })

// Log API response
logApiResponse({ url: '/api/projects', method: 'POST', status: 200, duration: 150 })

// Log error
logError({ error: new Error('Failed'), component: 'ProjectList', action: 'fetch' })

// Log user action
logUserAction({ action: 'create_project', category: 'projects', projectId: '123' })

// Log page view
logPageView('/projects', '/dashboard', 'proj-123')

// Log performance metric
logPerformance('api_response_time', 150, { endpoint: '/api/projects' })
```

---

## Correlation ID Management

```ts
import { getCorrelationId } from '@/lib/observability/correlation'

// Get current correlation ID (generates one if not exists)
const correlationId = getCorrelationId()

// Include in API requests
fetch('/api/projects', {
  headers: {
    'X-Correlation-ID': correlationId,
  },
})
```

All logs automatically include:
- `correlation_id` - Unique session/request identifier
- `trace_id` - OpenTelemetry trace ID
- `span_id` - OpenTelemetry span ID
- `service` - Service name
- `env` - Environment
- `version` - Application version
- `timestamp` - ISO 8601 timestamp

---

## PII Redaction

Sensitive fields are automatically redacted:

```ts
import { redactSensitiveData, redactSensitiveHeaders } from '@/lib/observability/logger'

// Automatically redacted fields
const sensitiveFields = [
  'password', 'token', 'secret', 'authorization',
  'cookie', 'apiKey', 'api_key', 'accessToken',
  'access_token', 'refreshToken', 'refresh_token',
  'creditCard', 'credit_card', 'ssn', 'socialSecurity',
]

// Usage
const safeData = redactSensitiveData({
  email: 'user@example.com',  // Kept
  password: 'secret123',      // Becomes '[REDACTED]'
  token: 'abc123',            // Becomes '[REDACTED]'
})
```

---

## Error Boundary with Observability

```tsx
// components/ErrorBoundary.tsx
import { ErrorBoundary } from '@/lib/observability/errorBoundary'

function App() {
  return (
    <ErrorBoundary
      fallback={<ErrorFallback />}
      onError={(error, errorInfo) => {
        // Error is automatically logged to Datadog
      }}
    >
      <MainContent />
    </ErrorBoundary>
  )
}
```

---

## Web Vitals Reporting

```ts
// lib/observability/webVitals.ts
import { reportWebVitals } from '@/lib/observability/webVitals'

// Automatically reports:
// - LCP (Largest Contentful Paint)
// - FID (First Input Delay)
// - CLS (Cumulative Layout Shift)
// - FCP (First Contentful Paint)
// - TTFB (Time to First Byte)

// Enable in setup
setupObservability({
  webVitals: { enabled: true },
})
```

---

## Log Sampling

Configure sampling to prevent log explosion:

```ts
// lib/observability/log-sampling.ts
export const samplingConfig = {
  // Sample rates by log level (0-1)
  levels: {
    debug: 0.1,   // 10% of debug logs
    info: 0.5,    // 50% of info logs
    warn: 1.0,    // 100% of warnings
    error: 1.0,   // 100% of errors
  },

  // Always sample certain operations
  alwaysSample: [
    'auth.login',
    'auth.logout',
    'payment.complete',
    'error.*',
  ],

  // Never sample (drop)
  neverSample: [
    'health_check',
    'heartbeat',
  ],
}
```

---

## PostHog Integration

```ts
// lib/analytics/posthog.ts
import posthog from 'posthog-js'

// Initialize
if (typeof window !== 'undefined') {
  posthog.init(process.env.NEXT_PUBLIC_POSTHOG_KEY!, {
    api_host: process.env.NEXT_PUBLIC_POSTHOG_HOST,
    capture_pageview: false, // Manual control
  })
}

// Track event
posthog.capture('project_created', {
  project_type: 'standard',
  has_description: true,
})

// Identify user
posthog.identify(userId, {
  email: user.email,
  plan: user.plan,
})

// Feature flags
if (posthog.isFeatureEnabled('new_dashboard')) {
  // Show new dashboard
}
```

---

## SLO Monitoring

```ts
import {
  recordPageLoad,
  recordApiCall,
  recordFrontendError,
  recordWebVitals,
  getSLOHealthSummary,
} from '@/lib/observability'

// Record page load
recordPageLoad('/projects', 1500) // path, duration in ms

// Record API call
recordApiCall('/api/projects', 200, 150) // endpoint, status, duration

// Record error
recordFrontendError('NetworkError', '/projects')

// Get SLO health summary
const health = getSLOHealthSummary()
// { availability: 99.9, latency: { p50: 100, p95: 250, p99: 500 } }
```

---

## Testing Observability

```ts
// lib/observability/__tests__/testability-examples.test.ts
import { setupObservability, resetObservability } from '@/lib/observability'
import { logger } from '@/lib/observability/logger'

describe('Observability', () => {
  beforeEach(() => {
    resetObservability()
  })

  it('should initialize successfully', () => {
    const result = setupObservability({
      serviceName: 'test-service',
      environment: 'test',
    })
    expect(result).toBe(true)
  })

  it('should log with correlation ID', () => {
    const spy = jest.spyOn(console, 'log')
    logger.info({ action: 'test' }, 'Test message')
    expect(spy).toHaveBeenCalled()
  })
})
```

---

## Dashboard & Alerting

### Datadog Dashboards

Create dashboards for:
- **Frontend Performance** - Web Vitals, page load times, JS errors
- **API Health** - Request rates, latency percentiles, error rates
- **User Journey** - Funnel analysis, session replay, user actions

### Recommended Alerts

| Alert | Condition | Severity |
|-------|-----------|----------|
| High Error Rate | Error rate > 1% for 5 min | Critical |
| Slow Page Loads | P95 > 3s for 10 min | Warning |
| API Latency Spike | P99 > 2s for 5 min | Warning |
| JS Errors Spike | > 100 errors/min | Critical |

---

## Anti-Patterns

<example type="invalid">
- Using `console.log` directly instead of structured logger (missing trace IDs)
- Hardcoding Datadog credentials in source code
- Not redacting sensitive data before logging
- Creating Pino child loggers per loop iteration (memory leak)
- Logging PII fields (password, token, cookie, etc.)
- Not using correlation IDs for request tracing
- Importing server-only OTEL code in client components
- Setting session replay sample rate to 100% in production (expensive)
- Not configuring log sampling (log explosion in production)
</example>

---

## Migration from Grafana/Pino

If migrating from the old Grafana/Pino stack:

1. Replace `pino` direct usage with `@/lib/observability/logger`
2. Update environment variables from `OTEL_*` to `NEXT_PUBLIC_DD_*`
3. Remove Grafana Agent configuration
4. Update dashboards to Datadog format
5. Ensure all logs include correlation IDs via the provided logger
