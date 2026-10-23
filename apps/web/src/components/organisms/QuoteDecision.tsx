import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { QuoteStatus } from '@/api/generated/types.gen'
import type { Answer } from '@/api/quotes'
import { formatAgencyDay } from '@/lib/format'

import { Button } from '../atoms/Button'

type Props = {
  /** Without it (the demo quote) the buttons are disabled and say why, so nobody believes they answered a real offer. */
  onDecide?: (answer: Answer, comment: string) => void
  status?: QuoteStatus
  /** ISO date-time: the end of the validity, or when the client answered. */
  validUntil?: string
  decidedAt?: string | null
  comment?: string | null
  /** The answer is on its way: both buttons wait. */
  pending?: boolean
  /** The answer did not go through, for a reason the client can retry. */
  failed?: boolean
}

/**
 * Accept or refuse the agency's offer, with an optional comment. Once the client answered, or
 * the offer expired, the buttons stay disabled and the panel says where the offer stands.
 */
export function QuoteDecision({ onDecide, status = 'open', validUntil, decidedAt, comment: givenComment, pending = false, failed = false }: Props) {
  const { t, i18n } = useTranslation('quote')
  const [comment, setComment] = useState('')
  const id = useId()
  const unavailable = !onDecide
  const closed = status !== 'open'
  const disabled = unavailable || closed || pending
  const day = (iso: string | null | undefined) => (iso ? formatAgencyDay(i18n.language, iso) : '')

  return (
    <aside aria-labelledby={`${id}-title`} className="bg-ink p-7 text-white md:sticky md:top-30">
      <h2 id={`${id}-title`} className="mb-3 text-[25px] tracking-normal">
        {t('decision.title')}
      </h2>
      {closed ? (
        <div role="status" className="text-sm leading-relaxed">
          <p className="font-semibold">
            {status === 'expired'
              ? t('decision.expired', { date: day(validUntil) })
              : t(status === 'accepted' ? 'decision.accepted' : 'decision.rejected', { date: day(decidedAt) })}
          </p>
          {givenComment && (
            <p className="mt-3 text-white/70">
              {t('decision.yourComment')} <q>{givenComment}</q>
            </p>
          )}
          <p className="mt-3 text-white/70">
            {t(status === 'rejected' ? 'decision.afterReject' : status === 'expired' ? 'decision.afterExpired' : 'decision.afterAccept')}
          </p>
        </div>
      ) : (
        <>
          <p className="text-sm leading-relaxed text-white/70">{t('decision.intro')}</p>
          <label htmlFor={id} className="sr-only">
            {t('decision.commentLabel')}
          </label>
          <textarea
            id={id}
            value={comment}
            disabled={disabled}
            maxLength={1000}
            onChange={(event) => setComment(event.target.value)}
            placeholder={t('decision.commentLabel')}
            className="my-4 h-22 w-full resize-none border border-white/20 bg-white/10 p-3 text-sm text-white placeholder:text-white/60 disabled:opacity-60"
          />
        </>
      )}
      <Button variant="coral" className="mt-4 w-full" disabled={disabled} onClick={() => onDecide?.('accept', comment)}>
        {t('decision.accept')}
      </Button>
      <Button variant="glass" className="mt-2.5 w-full" disabled={disabled} onClick={() => onDecide?.('reject', comment)}>
        {t('decision.refuse')}
      </Button>
      {pending && (
        <p role="status" className="mt-4 text-sm text-white/80">
          {t('decision.sending')}
        </p>
      )}
      {failed && (
        <p role="alert" className="mt-4 text-sm text-coral-light">
          {t('decision.failed')}
        </p>
      )}
      {!closed && !unavailable && <p className="mt-4 text-xs text-white/60">{t('decision.final')}</p>}
      {unavailable && <p className="mt-4 text-sm text-white/80">{t('decision.unavailable')}</p>}
      <small className="mt-5 block text-xs leading-normal text-white/60">{t('decision.noSupplier')}</small>
    </aside>
  )
}
