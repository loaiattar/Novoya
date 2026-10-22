import type { InputHTMLAttributes, TextareaHTMLAttributes } from 'react'

import { cn } from '@/lib/utils'

const field =
  'block w-full border border-line bg-white px-4 py-3.5 text-base text-ink placeholder:text-muted focus-visible:border-ink focus-visible:outline-none aria-invalid:border-danger read-only:bg-ivory'

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(field, className)} {...props} />
}

export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn(field, 'resize-none', className)} {...props} />
}
