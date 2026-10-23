import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { Photo } from '../atoms/Photo'
import { Eyebrow } from '../atoms/Eyebrow'
import { Jump } from '../atoms/Jump'
import { PublicHeader } from './PublicHeader'

type Props = {
  image: string
  imageAlt: string
  signedIn: boolean
  /** The calls to action under the copy. */
  actions: ReactNode
}

/** The landing page's first screen: full-height photo under navy, header, promise and actions. */
export function LandingHero({ image, imageAlt, signedIn, actions }: Props) {
  const { t } = useTranslation('home')
  return (
    <section className="relative h-svh min-h-[720px] overflow-hidden bg-ink text-ivory">
      <Photo
        src={image}
        alt={imageAlt}
        fetchPriority="high"
        className="absolute inset-0 size-full animate-zoom object-cover saturate-[0.82]"
      />
      <div
        aria-hidden="true"
        className="absolute inset-0 bg-[linear-gradient(180deg,rgb(22_35_63/0.75),transparent_22%),linear-gradient(90deg,rgb(22_35_63/0.9)_0%,rgb(22_35_63/0.7)_50%,rgb(22_35_63/0.35)),linear-gradient(0deg,rgb(22_35_63/0.8),transparent_40%)]"
      />
      <PublicHeader signedIn={signedIn} />
      <div className="absolute inset-x-6 top-[52%] -translate-y-1/2 md:right-auto md:left-[8vw] md:max-w-[900px]">
        <div className="animate-reveal">
          <Eyebrow light>{t('heroEyebrow')}</Eyebrow>
          <h1 className="mb-7 text-display-xl">
            {t('titleStart')}
            <br />
            <Jump text={t('titleEnd')} />
          </h1>
          <p className="mb-[34px] max-w-[620px] text-base leading-relaxed text-ivory/90 md:text-[19px]">
            {t('heroIntro')}
          </p>
          <div className="grid gap-2.5 md:flex">{actions}</div>
        </div>
      </div>
      <div
        aria-hidden="true"
        className="absolute inset-x-6 bottom-[30px] flex items-center gap-4 font-mono text-xs tracking-[0.14em] uppercase md:inset-x-[5vw]"
      >
        <span>01</span>
        <span className="h-px flex-1 bg-ivory/50 md:max-w-[50%]" />
        <span className="ml-auto">{t('heroFoot')}</span>
      </div>
    </section>
  )
}
