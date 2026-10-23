import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

/** A rounded label: a tag, a mood, a summary item. Not clickable; see TagToggle for that. */
export function Chip({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span className={cn('inline-block rounded-full border border-line px-2.5 py-1.5 text-xs', className)}>
      {children}
    </span>
  )
}
