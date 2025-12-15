---
description: Standards for integrating and customizing Shadcn UI components in Alpha Tales. Apply when adding, extending, or theming UI components to ensure consistency, accessibility, and maintainability.
globs:
alwaysApply: false
---

# Shadcn UI Integration Standards

## Critical Rules

- If this is applied, please add a comment to the top of the page "Shadcn rule applied"
- Use the Shadcn CLI to add components; avoid manual copying to ensure consistency.
- Place all Shadcn components in the `components/ui` directory.
- Maintain original component APIs when extending; prefer composition over modification.
- Customize styles using Tailwind CSS classes and the `cn` utility; avoid altering component source code directly.
- Implement theming using CSS variables defined in `globals.css`; avoid hardcoded color values.
- Ensure all components are accessible, preserving ARIA attributes and keyboard navigation.
- Use React Hook Form with Shadcn's form components for complex forms; use Server Actions for simple forms.
- For dialogs and modals, use Shadcn's Dialog component with proper focus management and accessibility features.
- Import components using absolute paths from `@/components/ui`.
- Document any extended or customized components thoroughly for team clarity.

---

## Component Structure

- **Directory Placement**: Store all Shadcn components in `components/ui`.
- **Naming Convention**: Use kebab-case for file names (e.g., `button.tsx`).
- **Exports**: Export components through index files for streamlined imports.

---

## Adding Components

- **Installation**: Use the Shadcn CLI with pnpm:

```sh
pnpm dlx shadcn@latest add [component-name]
```

- **Selective Addition**: Add components only as needed to keep the bundle size optimized.

---

## Customization Guidelines

- **Styling**: Use Tailwind CSS utility classes and the `cn` utility function to customize styles.
- **Extension**: Extend components through composition. For example:

```tsx
import { Button } from "@/components/ui/button"

export function SubmitButton({ children, ...props }) {
  return (
    <Button className="bg-blue-600 hover:bg-blue-700" {...props}>
      {children}
    </Button>
  )
}
```

- **Variants**: Utilize `class-variance-authority` (`cva`) for managing component variants.

---

## Theming and Dark Mode

- **CSS Variables**: Define theme variables in `globals.css`:

```css
:root {
  --background: #ffffff;
  --foreground: #000000;
  /* ...other variables */
}

.dark {
  --background: #0a0a0a;
  --foreground: #fafafa;
}
```

- **Tailwind Configuration**: Set `cssVariables` to `true` in `components.json` to enable CSS variable theming.
- **Dark Mode**: Use Tailwind's `dark:` class modifier to handle dark mode styles.

---

## Accessibility

- **ARIA Attributes**: Ensure components retain necessary ARIA attributes.
- **Keyboard Navigation**: Test components for proper keyboard interaction.
- **Focus States**: Maintain visible and consistent focus indicators.
- **Semantic HTML**: Use appropriate HTML elements to convey meaning.

---

## Form Handling

### With Server Actions (Simple Forms)

```tsx
'use client'

import { useActionState } from 'react'
import { useFormStatus } from 'react-dom'
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { createProject } from '@/app/actions/projects'

function SubmitButton() {
  const { pending } = useFormStatus()
  return (
    <Button type="submit" disabled={pending}>
      {pending ? 'Creating...' : 'Create Project'}
    </Button>
  )
}

export function ProjectForm() {
  const [state, formAction] = useActionState(createProject, null)

  return (
    <form action={formAction} className="space-y-4">
      <div>
        <Label htmlFor="name">Project Name</Label>
        <Input id="name" name="name" required />
        {state?.error && (
          <p className="text-sm text-red-500" role="alert">{state.error}</p>
        )}
      </div>
      <SubmitButton />
    </form>
  )
}
```

### With React Hook Form (Complex Forms)

```tsx
'use client'

import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Form, FormField, FormItem, FormLabel, FormControl, FormMessage } from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { projectSchema, type ProjectFormData } from '@/schemas/project'

export function ProjectFormComplex() {
  const form = useForm<ProjectFormData>({
    resolver: zodResolver(projectSchema),
    defaultValues: { name: '', description: '' },
  })

  const onSubmit = async (data: ProjectFormData) => {
    // Handle submission
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Project Name</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <Button type="submit" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting ? 'Creating...' : 'Create'}
        </Button>
      </form>
    </Form>
  )
}
```

---

## Dialogs and Modals

- **Component Usage**: Utilize Shadcn's Dialog component for modals.
- **Accessibility**: Ensure modals are dismissible via ESC key and backdrop clicks, and implement focus trapping.
- **Content**: Keep dialog content concise with clear action buttons.

```tsx
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"

export function ConfirmDialog({ onConfirm }) {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="destructive">Delete</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Are you sure?</DialogTitle>
          <DialogDescription>
            This action cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <div className="flex justify-end gap-2">
          <Button variant="outline">Cancel</Button>
          <Button variant="destructive" onClick={onConfirm}>Delete</Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
```

---

## Performance Considerations

- **Selective Imports**: Import only necessary components to reduce bundle size.
- **React 19 Compiler**: Let the compiler handle memoization automatically. Avoid excessive `React.memo`, `useMemo`, or `useCallback` unless profiler confirms a specific performance issue.
- **Code Splitting**: Use `next/dynamic` for large component trees:

```tsx
import dynamic from 'next/dynamic'

const HeavyChart = dynamic(() => import('@/components/HeavyChart'), {
  loading: () => <ChartSkeleton />,
})
```

---

## Examples

<example>
✅ Correct Usage
```tsx
// Component added using Shadcn CLI
// Customized using Tailwind CSS classes and cn utility
// Theming implemented via CSS variables
// Accessibility features preserved
// Server Action for form submission

'use client'

import { useActionState } from 'react'
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

export function SearchInput({ className, ...props }) {
  return (
    <div className={cn("relative", className)}>
      <Input
        type="search"
        placeholder="Search..."
        className="pr-10"
        aria-label="Search"
        {...props}
      />
    </div>
  )
}
```
</example>

<example type="invalid">
❌ Incorrect Usage
```tsx
// Component manually copied without using Shadcn CLI
// Styles modified directly within component source code
// Hardcoded color values used instead of CSS variables
// Missing ARIA attributes and improper keyboard navigation
// Excessive manual memoization

const Button = React.memo(({ children }) => {
  const handleClick = useCallback(() => {}, []) // Unnecessary
  return (
    <button
      style={{ backgroundColor: '#3b82f6' }}  // Hardcoded color
      onClick={handleClick}
    >
      {children}
    </button>
  )
})
```
</example>

---

## Anti-Patterns

- ❌ Manually copying components instead of using Shadcn CLI
- ❌ Modifying component source code directly
- ❌ Using hardcoded color values instead of CSS variables
- ❌ Missing ARIA attributes and focus indicators
- ❌ Excessive `React.memo`/`useMemo`/`useCallback` without profiler evidence
- ❌ Using API routes for form submissions (use Server Actions)
