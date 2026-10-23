import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

/** The small upper-case line above a heading. */
export function Eyebrow({
  children,
  light = false,
  className,
}: {
  children: ReactNode
  light?: boolean
  className?: string
}) {
  return (
    <p
      className={cn(
        'mb-6 font-mono text-xs leading-tight font-medium tracking-eyebrow uppercase',
        light ? 'text-white/75' : 'text-ink',
        className,
      )}
    >
      {children}
    </p>
  )
}
