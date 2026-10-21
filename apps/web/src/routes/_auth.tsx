import { createFileRoute, Outlet } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { HomeLink } from '../components/molecules/HomeLink'
import { AuthMedia } from '../components/organisms/AuthMedia'
import { AuthTemplate } from '../components/templates/AuthTemplate'

// The account pages, signed in or not: sign-in, sign-up, e-mail confirmation, lost password.
export const Route = createFileRoute('/_auth')({
  component: AuthLayout,
})

function AuthLayout() {
  const { t } = useTranslation('auth')
  return (
    <AuthTemplate
      media={
        <AuthMedia
          image="/images/aegean-boat"
          imageAlt={t('imageAlt')}
          logo={<HomeLink light />}
          quote={t('quote')}
          caption={t('caption')}
        />
      }
    >
      <Outlet />
    </AuthTemplate>
  )
}
