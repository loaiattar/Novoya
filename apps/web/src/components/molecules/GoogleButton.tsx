import { useTranslation } from 'react-i18next'

import { Button } from '../atoms/Button'
import { GoogleLogo } from '../atoms/GoogleLogo'

/**
 * "Continue with Google". A link, not a fetch: the browser goes to the API, which redirects
 * to Google and back.
 */
export function GoogleButton({ href }: { href: string }) {
  const { t } = useTranslation('auth')
  return (
    <Button asChild variant="outline" className="w-full">
      <a href={href}>
        <GoogleLogo />
        {t('continueWithGoogle')}
      </a>
    </Button>
  )
}
