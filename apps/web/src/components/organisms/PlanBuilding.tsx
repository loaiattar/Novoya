import { useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'

import { Eyebrow } from '../atoms/Eyebrow'
import { WishProgress } from './WishProgress'

// Up to a minute with free models: three steps of 8 s, then the last one waits.
const STEPS = ['answers', 'offers', 'days'] as const
const STEP_EVERY_MS = 8000

/**
 * What the client sees while their plan is built from the panel answers (up to a minute with
 * free models). The timed steps (#166) only show the page is not stuck; #32 can later replace
 * them with live progress.
 */
export function PlanBuilding() {
  const { t } = useTranslation('building')
  const title = useRef<HTMLHeadingElement>(null)

  // The form is gone: move the focus to the new title so screen readers announce the change.
  useEffect(() => title.current?.focus(), [])

  return (
    <main className="flex min-h-[calc(100vh-72px)] flex-col items-center justify-center bg-ink p-[30px] text-center text-white md:min-h-[calc(100vh-88px)]">
      <div className="relative mb-10 grid size-[150px] place-items-center rounded-full border border-white/15">
        <div aria-hidden="true" className="absolute size-[105px] motion-safe:animate-spin-slow rounded-full border-t border-coral" />
        <span aria-hidden="true" className="font-serif text-[38px] italic">
          N
        </span>
      </div>
      <Eyebrow light>{t('eyebrow')}</Eyebrow>
      <h1 ref={title} tabIndex={-1} className="mb-[30px] text-display-l outline-none">
        {t('titleStart')}
        <br />
        <em>{t('titleEnd')}</em>
      </h1>
      <div
        role="progressbar"
        aria-label={t('progressLabel')}
        aria-valuetext={t('progressValue')}
        className="h-0.5 w-[min(330px,80vw)] overflow-hidden bg-white/15"
      >
        <span className="block h-full w-[70%] animate-grow bg-coral" />
      </div>
      <WishProgress
        tone="dark"
        steps={STEPS.map((step) => t(`steps.${step}`))}
        everyMs={STEP_EVERY_MS}
        note={t('wait')}
        className="mt-[18px] max-w-[min(420px,85vw)]"
      />
      <p className="mt-2 max-w-[min(420px,85vw)] text-sm text-white/65">{t('status')}</p>
    </main>
  )
}
