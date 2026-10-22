import { cn } from '@/lib/utils'

const tones = {
  // Yellow ring on a light background.
  coral: 'ring-1 ring-coral ring-offset-2 ring-offset-paper',
  // Navy ring on a light background.
  ink: 'ring-1 ring-ink ring-offset-2 ring-offset-paper',
  // Light ring on a dark background.
  light: 'ring-1 ring-ivory/30',
}

/** The agency's round symbol: a "D" on navy, its "o" stepping up in yellow. Also the site
 * icon (public/icon-*.png). Decorative. */
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
      className={cn(
        'grid size-8 shrink-0 place-items-center rounded-full bg-ink font-serif font-extrabold leading-none text-ivory [container-type:inline-size]',
        tones[tone],
        className,
      )}
    >
      <span className="translate-y-[6%] text-[48cqi] tracking-[-0.04em]">
        D<span className="inline-block -translate-y-[0.32em] text-[0.62em] text-coral">o</span>
      </span>
    </span>
  )
}
