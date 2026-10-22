import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

import { SiteFooter } from '../organisms/SiteFooter'

/**
 * The frame of a signed-in page: room for the fixed header, then the page, then the site
 * footer. The page takes the free height, so the footer sits at the bottom of a short page.
 * `tone` is the page's background. A page with a bar fixed to the bottom of the screen adds
 * bottom padding through `className`, so the bar never covers the footer.
 */
export function AppShell({
  children,
  tone = 'paper',
  className,
}: {
  children: ReactNode
  tone?: 'paper' | 'ivory'
  className?: string
}) {
  return (
    <div
      className={cn(
        'flex min-h-screen flex-col pt-18 md:pt-22',
        tone === 'ivory' ? 'bg-ivory' : 'bg-paper',
        className,
      )}
    >
      <div className="flex flex-1 flex-col">{children}</div>
      <SiteFooter className="border-t border-line" />
    </div>
  )
}
