import { Photo } from '../atoms/Photo'
import type { ReactNode } from 'react'

type Props = {
  image: string
  imageAlt: string
  /** The brand, as a link home. */
  logo: ReactNode
  quote: string
  caption: string
}

/** The photo side of the sign-in page. On phones it shrinks to a band with the brand only. */
export function AuthMedia({ image, imageAlt, logo, quote, caption }: Props) {
  return (
    <section className="relative flex h-[250px] flex-col justify-end p-5 text-white md:h-auto md:px-[4vw] md:py-[42px]">
      <Photo src={image} alt={imageAlt} sizes="(min-width: 768px) 52vw, 100vw" fetchPriority="high" className="absolute inset-0 size-full object-cover" />
      <div
        aria-hidden="true"
        className="absolute inset-0 bg-[linear-gradient(180deg,rgb(22_35_63/0.85),transparent_200px),linear-gradient(0deg,rgb(22_35_63/0.65),rgb(22_35_63/0.05))]"
      />
      <div className="absolute top-5 left-5 md:top-10 md:left-[4vw]">{logo}</div>
      <blockquote className="relative mb-[25px] hidden max-w-[570px] font-serif text-[35px] leading-[1.2] font-extrabold tracking-[-0.025em] md:block">
        {quote}
      </blockquote>
      <p className="relative hidden text-xs tracking-[0.15em] uppercase md:block">{caption}</p>
    </section>
  )
}
