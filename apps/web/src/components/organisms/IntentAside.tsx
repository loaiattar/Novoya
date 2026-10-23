import { useTranslation } from 'react-i18next'

import { cn } from '@/lib/utils'

import { Eyebrow } from '../atoms/Eyebrow'

type Props = {
  /** The wish, in the client's words. */
  wish: string
  steps: string[]
  /** Index of the current step in `steps`. */
  current: number
}

/** The dark side panel: the wish being refined, and where the client is in the steps. */
export function IntentAside({ wish, steps, current }: Props) {
  const { t } = useTranslation('preferences')
  return (
    <aside className="relative bg-ink px-[22px] py-[35px] text-white md:px-[5vw] md:py-[90px]">
      <Eyebrow light>{t('intention')}</Eyebrow>
      <blockquote className="m-0 font-serif text-xl leading-normal md:text-[29px]">{t('wishQuote', { wish })}</blockquote>
      <ol aria-label={t('stepsLabel')} className="mt-[70px] hidden list-none items-center p-0 md:flex">
        {steps.map((step, index) => (
          <li key={step} className="flex items-center" aria-current={index === current ? 'step' : undefined}>
            {index > 0 && <span aria-hidden="true" className="h-px w-[50px] bg-white/20" />}
            <span
              className={cn(
                'grid size-[29px] place-items-center rounded-full border text-xs',
                index === current ? 'border-coral' : 'border-white/30 text-white/70',
              )}
            >
              <span aria-hidden="true">{index + 1}</span>
              <span className="sr-only">{step}</span>
            </span>
          </li>
        ))}
      </ol>
      <p className="mt-2.5 hidden text-sm text-white/65 md:block">{steps[current]}</p>
    </aside>
  )
}
