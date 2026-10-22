import { cn } from '@/lib/utils'

import { useAgency } from '../../hooks/ui/useAgency'
import { Jump } from './Jump'

/** The agency wordmark: the trade name in capitals, its "O" stepping aside in yellow. Wrap it
 * in a link to the home page where it is clickable. */
export function Logo({
  light = false,
  decorative = false,
  className,
}: {
  light?: boolean
  /** Hidden from screen readers when a parent link already names the agency. */
  decorative?: boolean
  className?: string
}) {
  const agency = useAgency()
  return (
    <span
      {...(decorative ? { 'aria-hidden': true } : { role: 'img', 'aria-label': agency.logo.alt })}
      className={cn(
        'pt-[0.3em] font-serif text-[26px] leading-none font-extrabold tracking-[-0.03em] uppercase md:text-[30px]',
        light ? 'text-ivory' : 'text-ink',
        className,
      )}
    >
      <Jump text={agency.tradeName.toUpperCase()} letter="O" />
    </span>
  )
}
