---
description: Standards for managing forms using React Hook Form, Zod, and React 19 hooks in Alpha Tales. Apply when creating or updating forms to ensure consistency, type safety, and optimal user experience.
globs:
alwaysApply: false
---

# Form Handling Standards

## Critical Rules

- If this is applied, please add a comment to the top of the page "Form handling rule applied"
- Use **React Hook Form** (7.55.0) for complex form state management
- Use **Zod** (3.25.76) for schema validation via `zodResolver`
- Use **React 19 hooks** (`useFormStatus`, `useActionState`, `useOptimistic`) for Server Action forms
- Use **Server Actions** with `"use server"` for form submissions instead of API routes
- Define schemas in centralized `schemas/` directory with `z.infer` type exports
- Validate on both client (immediate feedback) and server (security)
- Disable submissions during processing to prevent duplicates
- Maintain accessibility with ARIA attributes and keyboard navigation

---

## React 19 Form Patterns (Preferred)

### Server Actions with useActionState

```tsx
// app/actions/projects.ts
'use server'

import { z } from 'zod'
import { auth } from '@/auth'
import { revalidatePath } from 'next/cache'

const schema = z.object({
  name: z.string().min(1, 'Name is required').max(100),
  description: z.string().max(1000).optional(),
})

type ActionState = { error?: string; success?: boolean } | null

export async function createProject(
  prevState: ActionState,
  formData: FormData
): Promise<ActionState> {
  const session = await auth({ ensureSignedIn: true })

  const validated = schema.safeParse(Object.fromEntries(formData))
  if (!validated.success) {
    return { error: validated.error.errors[0].message }
  }

  try {
    await db.projects.create({
      data: { ...validated.data, userId: session.user.id }
    })
    revalidatePath('/projects')
    return { success: true }
  } catch (error) {
    return { error: 'Failed to create project' }
  }
}
```

```tsx
// components/ProjectForm.tsx
'use client'

import { useActionState } from 'react'
import { useFormStatus } from 'react-dom'
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
        <Input id="name" name="name" required aria-describedby="name-error" />
        {state?.error && (
          <p id="name-error" className="text-sm text-red-500" role="alert">
            {state.error}
          </p>
        )}
      </div>
      <SubmitButton />
      {state?.success && (
        <p className="text-sm text-green-500">Project created successfully!</p>
      )}
    </form>
  )
}
```

### useOptimistic for Instant Feedback

```tsx
'use client'

import { useOptimistic, useTransition } from 'react'
import { addTodo } from '@/app/actions/todos'

export function TodoList({ todos }: { todos: Todo[] }) {
  const [optimisticTodos, addOptimistic] = useOptimistic(
    todos,
    (state, newTodo: Todo) => [...state, { ...newTodo, pending: true }]
  )
  const [_, startTransition] = useTransition()

  async function handleSubmit(formData: FormData) {
    const newTodo = {
      id: crypto.randomUUID(),
      text: formData.get('text') as string,
    }

    startTransition(() => addOptimistic(newTodo))
    await addTodo(formData)
  }

  return (
    <div>
      <form action={handleSubmit}>
        <Input name="text" required />
        <SubmitButton />
      </form>
      <ul>
        {optimisticTodos.map(todo => (
          <li key={todo.id} className={todo.pending ? 'opacity-50' : ''}>
            {todo.text}
          </li>
        ))}
      </ul>
    </div>
  )
}
```

---

## React Hook Form (Complex Forms)

Use React Hook Form for complex forms with many fields, multi-step wizards, or dynamic fields:

```tsx
// schemas/projectSchema.ts
import { z } from 'zod'

export const projectSchema = z.object({
  name: z.string().min(1, 'Name is required').max(100),
  description: z.string().max(1000).optional(),
  category: z.enum(['web', 'mobile', 'api']),
  team: z.array(z.string().email()).min(1, 'At least one team member required'),
})

export type ProjectFormData = z.infer<typeof projectSchema>
```

```tsx
// features/projects/hooks/useProjectForm.ts
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { projectSchema, type ProjectFormData } from '@/schemas/projectSchema'
import { createProject } from '@/app/actions/projects'

export function useProjectForm() {
  const form = useForm<ProjectFormData>({
    resolver: zodResolver(projectSchema),
    defaultValues: {
      name: '',
      description: '',
      category: 'web',
      team: [],
    },
  })

  const onSubmit = async (data: ProjectFormData) => {
    const formData = new FormData()
    Object.entries(data).forEach(([key, value]) => {
      if (Array.isArray(value)) {
        value.forEach(v => formData.append(key, v))
      } else {
        formData.append(key, value)
      }
    })
    await createProject(null, formData)
  }

  return { form, onSubmit }
}
```

```tsx
// components/ProjectFormComplex.tsx
'use client'

import { useProjectForm } from '@/features/projects/hooks/useProjectForm'
import { Form, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'

export function ProjectFormComplex() {
  const { form, onSubmit } = useProjectForm()

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Project Name</FormLabel>
              <Input {...field} />
              <FormMessage />
            </FormItem>
          )}
        />
        <Button type="submit" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting ? 'Creating...' : 'Create Project'}
        </Button>
      </form>
    </Form>
  )
}
```

---

## Schema Definition Best Practices

```ts
// schemas/index.ts - Centralized schema exports
export * from './userSchema'
export * from './projectSchema'
export * from './authSchema'

// schemas/userSchema.ts
import { z } from 'zod'

export const PASSWORD_MIN_LENGTH = 8
export const NAME_MAX_LENGTH = 100

export const userSchema = z.object({
  email: z.string().email('Invalid email address'),
  password: z
    .string()
    .min(PASSWORD_MIN_LENGTH, `Password must be at least ${PASSWORD_MIN_LENGTH} characters`),
  name: z.string().min(1).max(NAME_MAX_LENGTH).trim(),
})

// Cross-field validation
export const passwordConfirmSchema = z
  .object({
    password: z.string().min(8),
    confirmPassword: z.string(),
  })
  .refine(data => data.password === data.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  })

export type UserFormData = z.infer<typeof userSchema>
```

---

## When to Use Each Pattern

| Pattern | Use Case |
|---------|----------|
| Server Action + `useActionState` | Simple forms, single submit |
| Server Action + `useOptimistic` | Lists with optimistic updates |
| React Hook Form + Zod | Complex forms, many fields, validation |
| React Hook Form + Multi-step | Wizards, onboarding flows |

---

## Accessibility Requirements

```tsx
// Accessible form field pattern
<FormField
  control={form.control}
  name="email"
  render={({ field, fieldState }) => (
    <FormItem>
      <FormLabel htmlFor="email">Email</FormLabel>
      <Input
        {...field}
        id="email"
        type="email"
        aria-invalid={!!fieldState.error}
        aria-describedby={fieldState.error ? 'email-error' : undefined}
      />
      {fieldState.error && (
        <p id="email-error" role="alert" className="text-sm text-red-500">
          {fieldState.error.message}
        </p>
      )}
    </FormItem>
  )}
/>
```

**Requirements:**
- ✅ Associate labels with inputs via `htmlFor`/`id`
- ✅ Use `aria-invalid` for error states
- ✅ Use `aria-describedby` to link error messages
- ✅ Use `role="alert"` for error messages
- ✅ Ensure keyboard navigation works
- ✅ Provide visible focus indicators

---

## Examples

<example>
✅ Modern Form with Server Action
```tsx
'use client'
import { useActionState } from 'react'
import { useFormStatus } from 'react-dom'
import { submitFeedback } from '@/app/actions/feedback'

function SubmitButton() {
  const { pending } = useFormStatus()
  return <Button disabled={pending}>{pending ? 'Sending...' : 'Send'}</Button>
}

export function FeedbackForm() {
  const [state, formAction] = useActionState(submitFeedback, null)
  return (
    <form action={formAction}>
      <Textarea name="message" required aria-label="Feedback message" />
      <SubmitButton />
      {state?.error && <p role="alert">{state.error}</p>}
    </form>
  )
}
```
</example>

<example type="invalid">
❌ Old Pattern (Avoid)
```tsx
'use client'
export function FeedbackForm() {
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    await fetch('/api/feedback', { method: 'POST', body: new FormData(e.target) })
    setLoading(false)
  }

  // Use Server Actions instead of API routes!
}
```
</example>

---

## Anti-Patterns

- ❌ Using API routes for form submissions (use Server Actions)
- ❌ Schema defined inline in components
- ❌ No loading state during submission
- ❌ Missing ARIA attributes
- ❌ Client-only validation without server validation
- ❌ Manual `useState` for form state (use React Hook Form or Server Actions)
