---
description: Standards for using Tailwind CSS in Alpha Tales. Apply whenever styling or theming UI to ensure performance, accessibility, and consistent class structure.
globs:
alwaysApply: false
---

# Tailwind-CSS Standards

## Critical Rules

- If this is applied, please add a comment to the top of the page "Tailwind standards rule applied"
- **Use the `cn()` helper** (or `clsx`) for conditional classes; never build class strings manually.
- **Let Prettier's Tailwind plugin sort classes automatically** to enforce the order: layout → sizing → spacing → typography → visual → state → custom.
- **JIT is default** in Tailwind 3.4.1+; no need to set `mode: 'jit'` in config (deprecated).
- **Dark mode** must use the `dark:` variant; colours must pass WCAG contrast (≥ 4.5:1).
- **Responsive utilities** follow a mobile-first pattern with standard breakpoints; avoid excessive combinations.
- **Variants with class-variance-authority (`cva`)** power component themes; default variants required.
- **Dynamic classes** must be whitelisted via `safelist` or full-string conditionals to survive purging.
- **Custom utilities** live inside `@layer utilities` and follow Tailwind naming rules.
- **Accessibility**: every interactive element needs visible focus, semantic tags, and compliant contrast.
- **Images** must use `next/image` with `fill` or explicit dimensions plus Tailwind classes for responsiveness.
- **Prettier must run with `prettier-plugin-tailwindcss`** (add the plugin last in the `.prettierrc` `plugins` array) so class names are auto-sorted.
- **ESLint configuration must extend `"plugin:tailwindcss/recommended"`** to flag unknown, duplicate, or mis-ordered utilities at lint time.

---

## Tailwind Configuration (v3.4.1+)

```js
// tailwind.config.js
/** @type {import('tailwindcss').Config} */
module.exports = {
  // JIT is now default - no mode setting needed
  content: ['./src/**/*.{ts,tsx,html}', './app/**/*.{ts,tsx}'],
  darkMode: 'class',
  safelist: ['bg-status-success', 'bg-status-error'], // Dynamic classes only
  theme: {
    extend: {
      colors: {
        // Use CSS variables for theming
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: 'hsl(var(--primary))',
      },
    },
  },
  plugins: [],
}
```

**Note**: `mode: 'jit'` is deprecated and no longer needed. JIT compilation is the default behavior in Tailwind CSS 3.x.

---

## Class-Ordering & `cn()` Pattern

```tsx
<div
  className={cn(
    // Layout
    'flex flex-col',
    // Size
    'w-full max-w-md',
    // Spacing
    'p-4 gap-2',
    // Typography
    'text-sm font-medium',
    // Visual
    'bg-white dark:bg-gray-800 rounded-lg shadow-md',
    // State
    isActive && 'border-blue-500',
    className,
  )}
/>
```

Prettier sorts the inline lists; multiline arrays improve readability.

---

## Dark-Mode & Theme Tokens

- Use `dark:` variant only; no separate "_dark" CSS files.
- Colours defined as CSS variables in `globals.css`; theme switch updates the `html` class.
- Validate contrast with tools such as Lea Verou's contrast-ratio checker.

```css
/* globals.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    --primary: 222.2 47.4% 11.2%;
    /* ... */
  }

  .dark {
    --background: 222.2 84% 4.9%;
    --foreground: 210 40% 98%;
    --primary: 210 40% 98%;
    /* ... */
  }
}
```

---

## Responsive & Accessibility Patterns

| Concern | Practice |
|---------|----------|
| Breakpoints | `sm`, `md`, `lg`, `xl`, `2xl` only |
| Focus states | `focus-visible:outline-none focus-visible:ring-2` |
| Colour contrast | Tailwind palette + WCAG checks (≥ 4.5:1) |

---

## Variant Management with CVA

```ts
import { cva } from 'class-variance-authority'

export const buttonVariants = cva(
  'inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50',
  {
    variants: {
      variant: {
        primary: 'bg-primary text-white hover:bg-primary/90',
        ghost: 'hover:bg-muted',
        destructive: 'bg-red-600 text-white hover:bg-red-700',
      },
      size: {
        sm: 'h-9 px-3',
        md: 'h-10 px-4',
        lg: 'h-11 px-8',
      },
    },
    defaultVariants: { variant: 'primary', size: 'md' },
  },
)
```

Ensures predictable, typed variant combinations.

---

## Custom Utilities & Safelisting

```css
/* src/styles/utilities.css */
@layer utilities {
  .bg-status-success {
    @apply bg-green-600 text-white;
  }
  .bg-status-error {
    @apply bg-red-600 text-white;
  }
}
```

Only safelist indispensable dynamic classes to prevent bloat:

```js
// tailwind.config.js
module.exports = {
  safelist: ['bg-status-success', 'bg-status-error'],
  // ...
}
```

---

## Dynamic Class Patterns

```tsx
// CORRECT: Full string conditionals survive purging
const statusClass = status === 'success' ? 'bg-green-500' : 'bg-red-500'

// INCORRECT: String interpolation breaks JIT purging
const badClass = `bg-${color}-500` // ❌ Will be purged
```

---

## Examples

<example>
✅ Correct Pattern
```tsx
// Uses cn() with proper class ordering
// Colour tokens defined as CSS variables
// cva handles button variants
// Responsive modifiers limited to sm + lg
// No deprecated mode: 'jit' config

import { cn } from '@/lib/utils'
import { buttonVariants } from './button.variants'

export function ActionButton({ variant, size, className, ...props }) {
  return (
    <button
      className={cn(
        buttonVariants({ variant, size }),
        'focus-visible:ring-2',
        className
      )}
      {...props}
    />
  )
}
```
</example>

<example type="invalid">
❌ Incorrect Pattern
```tsx
// Manual string concatenation breaks JIT
const size = 'lg'
className={'p-' + size}  // ❌ Breaks purging

// Hard-coded hex colours with poor contrast
style={{ backgroundColor: '#ccc', color: '#ddd' }}  // ❌ Low contrast

// Custom CSS outside @layer utilities overriding core styles
.my-button { padding: 20px; }  // ❌ Not in @layer

// Deprecated JIT mode setting
module.exports = {
  mode: 'jit',  // ❌ Deprecated, remove this
}
```
</example>

---

## Anti-Patterns

- ❌ Manual string concatenation for classes (`'p-'+size`)
- ❌ Hard-coded hex colours instead of CSS variables
- ❌ Poor colour contrast failing WCAG standards
- ❌ Custom CSS outside `@layer utilities` overriding core styles
- ❌ Setting `mode: 'jit'` (deprecated in Tailwind 3.x)
- ❌ Missing focus indicators on interactive elements
- ❌ Excessive breakpoint combinations
- ❌ Dynamic class interpolation without safelisting
