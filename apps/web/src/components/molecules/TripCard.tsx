import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

import { Photo } from '../atoms/Photo'

type Props = {
  image: string
  imageAlt: string
  /** The small round label on the photo ("01"). */
  badge: string
  place: string
  title: string
  copy: string
  /** The link around the card (a router `Link`), given the card's content. */
  renderLink: (content: ReactNode) => ReactNode
  className?: string
}

/** An inspiration: photo, place, title and a line. The whole card is one link. */
export function TripCard({ image, imageAlt, badge, place, title, copy, renderLink, className }: Props) {
  return (
    <article className={cn('group', className)}>
      {renderLink(
        <>
          <div className="relative mb-6 h-[420px] overflow-hidden rounded-2xl md:h-[520px]">
            <Photo
              src={image}
              sizes="(min-width: 768px) 30vw, 84vw"
              alt={imageAlt}
              loading="lazy"
              className="size-full object-cover saturate-[0.84] transition-transform duration-600 group-hover:scale-[1.04]"
            />
            <span
              aria-hidden="true"
              className="absolute top-3.5 right-3.5 grid size-[42px] place-items-center rounded-full bg-sky font-mono text-xs font-medium"
            >
              {badge}
            </span>
          </div>
          <p className="m-0 font-mono text-xs font-medium tracking-[0.12em] uppercase">{place}</p>
          <h3 className="mt-1.5 mb-2.5 font-serif text-[30px] leading-[1.04] font-extrabold tracking-[-0.025em] lowercase md:text-[34px]">
            {title}
          </h3>
          <p className="m-0 text-sm text-muted">{copy}</p>
        </>,
      )}
    </article>
  )
}
