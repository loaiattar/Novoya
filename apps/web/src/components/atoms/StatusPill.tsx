import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

/** A trip or quote status. `highlight` is for the one that needs the client's attention. */
export function StatusPill({
  children,
  highlight = false,
  className,
}: {
  children: ReactNode
  highlight?: boolean
  className?: string
}) {
  return (
    <span
      className={cn(
        'inline-block rounded-full px-2.5 py-1.5 text-xs font-medium uppercase',
        highlight ? 'bg-coral' : 'bg-sage',
        className,
      )}
    >
      {children}
    </span>
  )
}
