import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { Photo } from '../atoms/Photo'
import { Eyebrow } from '../atoms/Eyebrow'
import { Seal } from '../atoms/Seal'

const display = 'm-0 text-[50px] leading-[0.95] md:text-[clamp(60px,7vw,104px)]'

/** The promise and the honesty pledge. */
export function Manifesto() {
  const { t } = useTranslation('home')
  return (
    <section className="bg-ivory px-6 py-[90px] md:px-[8vw] md:pt-[150px] md:pb-[140px]">
      <Eyebrow>{t('manifesto.eyebrow')}</Eyebrow>
      <h2 className={display}>
        {t('manifesto.titleStart')}
        <br />
        <em>{t('manifesto.titleEnd')}</em>
      </h2>
      <div className="mt-[45px] md:mt-[70px] md:ml-[17vw] md:grid md:grid-cols-[1.2fr_1fr] md:gap-[16vw]">
        <p className="font-serif text-[19px] leading-[1.55] md:text-2xl">
          {t('manifesto.lead')}
        </p>
        <div className="mt-[45px] flex items-start gap-6 leading-[1.65] text-muted md:mt-0">
          <Seal className="size-[58px]" />
          <p>
            <strong className="text-ink">{t('manifesto.honestyTitle')}</strong>
            <br />
            {t('manifesto.honestyText')}
          </p>
        </div>
      </div>
    </section>
  )
}

/** The most wanted trips: a heading, then the trip cards given as children. */
export function PopularTrips({ children }: { children: ReactNode }) {
  const { t } = useTranslation('home')
  return (
    <section id="voyages" aria-labelledby="voyages-title" className="bg-paper px-6 py-[90px] md:px-[5vw] md:py-[140px]">
      <div className="mb-[45px] md:mx-[3vw] md:mb-[75px] md:flex md:items-end md:justify-between">
        <div>
          <Eyebrow>{t('popular.eyebrow')}</Eyebrow>
          <h2 id="voyages-title" className="m-0 text-[50px] leading-[0.95] md:text-[78px]">
            {t('popular.title')}
          </h2>
        </div>
        <p className="mt-5 max-w-[390px] leading-[1.7] text-muted md:mt-0">
          {t('popular.intro')}
        </p>
      </div>
      <div className="-mr-6 flex snap-x snap-mandatory gap-5 overflow-x-auto md:mr-0 md:grid md:grid-cols-[1.25fr_0.92fr_0.92fr] md:items-start md:overflow-visible [&>*]:min-w-[84vw] [&>*]:snap-start md:[&>*]:min-w-0">
        {children}
      </div>
    </section>
  )
}

const STEPS = [
  ['01', 'describe'],
  ['02', 'refine'],
  ['03', 'discover'],
  ['04', 'exchange'],
] as const

/** From the wish to departure: the four steps, on ink. */
export function Method() {
  const { t } = useTranslation('home')
  return (
    <section
      id="methode"
      className="bg-ink px-6 py-[90px] text-white md:grid md:grid-cols-[0.85fr_1.7fr] md:gap-[10vw] md:px-[8vw] md:py-[145px]"
    >
      <div>
        <Eyebrow light>{t('method.eyebrow')}</Eyebrow>
        <h2 className="text-[52px] leading-[0.98] md:text-[75px]">
          {t('method.titleStart')}
          <br />
          {t('method.titleEnd')}
        </h2>
        <p className="max-w-[350px] leading-[1.7] text-white/65">
          {t('method.intro')}
        </p>
      </div>
      <ol className="mt-[55px] list-none p-0 md:mt-0 md:grid md:grid-cols-2">
        {STEPS.map(([number, step]) => (
          <li key={number} className="pt-[15px] pb-[55px] md:pr-10">
            <span className="font-serif text-sm text-coral">{number}</span>
            <div aria-hidden="true" className="mt-[18px] mb-7 h-px bg-white/20" />
            <h3 className="font-serif text-[25px] font-normal">{t(`method.steps.${step}.title`)}</h3>
            <p className="max-w-[240px] text-[13px] leading-[1.6] text-white/65">{t(`method.steps.${step}.copy`)}</p>
          </li>
        ))}
      </ol>
    </section>
  )
}

const PROMISES = [
  ['01', 'realOffers'],
  ['02', 'noPrice'],
  ['03', 'yourWords'],
] as const

/** Nothing made up, nothing intrusive: three promises. */
export function Trust() {
  const { t } = useTranslation('home')
  return (
    <section className="bg-ivory px-6 py-[90px] md:grid md:grid-cols-[1.1fr_1fr] md:gap-[12vw] md:px-[8vw] md:py-[150px]">
      <div>
        <Eyebrow>{t('trust.eyebrow')}</Eyebrow>
        <h2 className="m-0 text-[50px] leading-[0.95] md:text-[72px]">
          {t('trust.titleStart')}
          <br />
          {t('trust.titleEnd')}
        </h2>
      </div>
      <ul className="mt-[50px] min-w-0 list-none p-0 md:mt-0">
        {PROMISES.map(([number, promise]) => (
          <li
            key={number}
            className="grid grid-cols-[30px_1fr] gap-5 border-t border-line py-[27px] lg:grid-cols-[40px_180px_1fr]"
          >
            <span className="font-serif text-coral-text">{number}</span>
            <h3 className="m-0 font-serif text-[21px] font-normal">{t(`trust.promises.${promise}.title`)}</h3>
            <p className="col-start-2 m-0 text-[13px] leading-[1.6] text-muted lg:col-start-auto">{t(`trust.promises.${promise}.copy`)}</p>
          </li>
        ))}
      </ul>
    </section>
  )
}

/** The last call to action over a photo. */
export function Closing({ image, action }: { image: string; action: ReactNode }) {
  const { t } = useTranslation('home')
  return (
    <section className="relative grid h-[600px] place-items-center text-center text-white md:h-[720px]">
      <Photo src={image} alt="" loading="lazy" className="absolute inset-0 size-full object-cover" />
      <div aria-hidden="true" className="absolute inset-0 bg-[rgb(11_36_31/0.6)]" />
      <div className="relative px-6">
        <Eyebrow light>{t('closing.eyebrow')}</Eyebrow>
        <h2 className="mb-[35px] text-[55px] leading-[0.95] md:text-[90px]">
          {t('closing.titleStart')}
          <br />
          <em>{t('closing.titleEnd')}</em>
        </h2>
        {action}
      </div>
    </section>
  )
}
