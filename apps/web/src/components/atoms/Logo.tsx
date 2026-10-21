import { cn } from '@/lib/utils'

import { useAgency } from '../../hooks/ui/useAgency'
import { Photo } from './Photo'

/** The agency wordmark. Wrap it in a link to the home page where it is clickable. */
export function Logo({
  light = false,
  decorative = false,
  className,
}: {
  light?: boolean
  /** Empty alt when a parent link already names the agency. */
  decorative?: boolean
  className?: string
}) {
  const agency = useAgency()
  return (
    <Photo
      src={agency.logo.src}
      alt={decorative ? '' : agency.logo.alt}
      width={agency.logo.width}
      height={agency.logo.height}
      sizes="160px"
      // The logo's size (3:1), so the header keeps its space while the image loads.
      width={1536}
      height={512}
      className={cn('h-8 w-auto max-w-[min(100%,11rem)] object-contain md:h-10', light && 'bg-white/95 p-1', className)}
    />
  )
}
