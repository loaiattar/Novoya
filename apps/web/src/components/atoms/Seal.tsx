import { cn } from '@/lib/utils'

const tones = {
  // Coral ring on a light background.
  coral: 'border border-coral',
  // Ink ring, for the concierge in conversations.
  ink: 'border border-ink',
  // White ring on a dark background.
  light: 'border border-white/30',
}

/** The agency's round "D" symbol, in several sizes. Decorative. */
export function Seal({
  tone = 'coral',
  className,
}: {
  tone?: keyof typeof tones
  className?: string
}) {
  return (
    <span
      aria-hidden="true"
      className={cn('grid size-8 shrink-0 place-items-center overflow-hidden rounded-full bg-white', tones[tone], className)}
    >
      {/* The agency's symbol (brand/images/favicon.png), also the site icon. 192 px is sharp up to 64 px on 3× screens. */}
      <img src="/icon-192.png" alt="" width={192} height={192} className="size-[70%] object-contain" />
    </span>
  )
}
