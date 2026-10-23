import { useQuery } from '@tanstack/react-query'
import { useRouteContext } from '@tanstack/react-router'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { getMeOptions } from '../../api/generated/@tanstack/react-query.gen'
import type { MeResponse, UpdateMeRequest } from '../../api/generated/types.gen'
import { useUpdateMe, useUpdateMeBusy } from '../../hooks/i18n/useUpdateMe'
import { useAccountErrors } from '../../routes/-accountErrors'
import { ProfileForm, type Profile } from './ProfileForm'

const profileOf = (me: MeResponse): Profile => ({
  firstName: me.first_name ?? '',
  lastName: me.last_name ?? '',
  locale: me.locale,
})

/** Only what differs from what is stored. An empty name that was never stored stays unsent. */
function changes(stored: MeResponse, edited: Profile): UpdateMeRequest {
  const body: UpdateMeRequest = {}
  const firstName = edited.firstName.trim()
  const lastName = edited.lastName.trim()
  if (firstName !== (stored.first_name ?? '')) body.first_name = firstName
  if (lastName !== (stored.last_name ?? '')) body.last_name = lastName
  if (edited.locale !== stored.locale) body.locale = edited.locale
  return body
}

/** The "Personal information" tab on My trips: GET /me, saved with PATCH /me. */
export function ProfileTab() {
  const { t } = useTranslation('profile')
  // Read like useLanguageChoice: the cache, never fetched here, and the user the signed-in
  // layout loaded when the idle check has dropped the cache. The form never unmounts.
  const loaded = useRouteContext({ from: '/_authenticated', select: (context) => context.me })
  const cached = useQuery({ ...getMeOptions(), enabled: false })
  const me = cached.data ?? loaded
  const save = useUpdateMe()
  // Also while the header's language switch saves.
  const busy = useUpdateMeBusy()
  const errors = useAccountErrors(save.error)
  // Saved with nothing left to send: what is shown is what is stored.
  const [upToDate, setUpToDate] = useState(false)

  return (
    <ProfileForm
      profile={profileOf(me)}
      email={me.email}
      // A Google account can come without a last name: it may stay empty.
      required={{ firstName: me.first_name !== null, lastName: me.last_name !== null }}
      onSubmit={async (edited) => {
        const body = changes(me, edited)
        if (Object.keys(body).length === 0) {
          // No request: drop the error of an earlier failed save, and confirm.
          save.reset()
          setUpToDate(true)
          return profileOf(me)
        }
        setUpToDate(false)
        return profileOf(await save.mutateAsync({ body }))
      }}
      pending={busy}
      errors={{ firstName: errors.firstName, lastName: errors.lastName, form: errors.form }}
      success={save.isSuccess || upToDate ? t('saved') : undefined}
    />
  )
}
