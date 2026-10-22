import { Link, type LinkProps } from '@tanstack/react-router'
import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

export type BackofficeItem = {
  label: string
  /** For a section without a page yet: shown as the current one. */
  active?: boolean
  /** null: still loading; the badge keeps its place so the links beside it do not move. */
  count?: number | null
  /** The section's page. The link is the current one (aria-current) while it is open. */
  to?: LinkProps['to']
  /** Current only on that exact page, not on the pages under it. */
  exact?: boolean
}

type Props = {
  /** The area's name, above the side links. */
  area: string
  items: BackofficeItem[]
  children: ReactNode
}

const itemClass = 'flex min-h-11 items-center justify-between gap-2 rounded-[3px] p-3 text-sm whitespace-nowrap'
const currentClass = 'bg-ivory font-semibold'

/**
 * The agency and admin pages: the sections, then the content. On a desktop the sections are a
 * side list; on a phone, when they have pages, a row above the content that scrolls sideways.
 * It takes the free height of the page frame, so the side list reaches the footer.
 */
export function BackofficeLayout({ area, items, children }: Props) {
  // Sections without pages yet (the agency area) stay a desktop list: nothing to open on a phone.
  const linked = items.some((item) => item.to)
  return (
    <div className="flex-1 md:grid md:grid-cols-[220px_1fr]">
      <aside
        aria-label={area}
        className={cn(
          'border-line md:flex md:flex-col md:gap-1 md:border-e md:border-b-0 md:px-5.5 md:py-10',
          linked ? 'border-b' : 'hidden',
        )}
      >
        <small className="mx-3 mb-5 hidden text-xs tracking-[0.15em] text-muted uppercase md:block">{area}</small>
        <ul className="flex gap-1 overflow-x-auto px-5 py-2 md:flex-col md:overflow-visible md:p-0">
          {items.map((item) => {
            const count = item.count !== undefined && (
              <b className={cn('rounded-full bg-coral px-1.5 text-xs', item.count === null && 'invisible')}>{item.count ?? 0}</b>
            )
            if (item.to) {
              return (
                <li key={item.label} className="shrink-0">
                  <Link
                    to={item.to}
                    activeOptions={{ exact: item.exact ?? false }}
                    className={cn(itemClass, 'no-underline')}
                    activeProps={{ className: currentClass }}
                    inactiveProps={{ className: 'text-muted' }}
                  >
                    {item.label}
                    {count}
                  </Link>
                </li>
              )
            }
            return (
              <li
                key={item.label}
                aria-current={item.active ? 'page' : undefined}
                className={cn(itemClass, 'shrink-0', item.active ? currentClass : 'text-muted')}
              >
                {item.label}
                {count}
              </li>
            )
          })}
        </ul>
      </aside>
      <main className="px-5 py-11 md:px-[5vw] md:py-14">{children}</main>
    </div>
  )
}
