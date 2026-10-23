import { useQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { googleSignInUrl } from '../api/auth'
import { getMeOptions, listFeaturedOffersOptions } from '../api/generated/@tanstack/react-query.gen'
import { Button } from '../components/atoms/Button'
import { GoogleLogo } from '../components/atoms/GoogleLogo'
import { TripCard } from '../components/molecules/TripCard'
import { LandingHero } from '../components/organisms/LandingHero'
import { Advisors, Closing, Manifesto, Method, PopularTrips, Reviews } from '../components/organisms/LandingSections'
import { SiteFooter } from '../components/organisms/SiteFooter'
import { destinationPhoto } from '../domain/wish/destination'
import { localizeCountry } from '../lib/countries'

export const Route = createFileRoute('/')({
  component: LandingPage,
})

function LandingPage() {
  // Visitors are welcome: a 401 here only means "not signed in".
  const me = useQuery({ ...getMeOptions(), retry: false })
  const signedIn = me.isSuccess
  // The offers an agent featured, as inspirations. Never let a section break the landing page:
  // anything but a list (loading, error) shows no section.
  const featured = useQuery({ ...listFeaturedOffersOptions(), retry: false })
  const offers = Array.isArray(featured.data) ? featured.data : []
  const { t, i18n } = useTranslation('home')

  return (
    <>
      <main>
        <LandingHero
          image="/images/train-reader"
          imageAlt={t('heroImageAlt')}
          signedIn={signedIn}
          actions={
            <>
              <Button asChild variant="coral" size="lg">
                <Link to="/wish">
                  {t('describeTrip')} <span aria-hidden="true">↗</span>
                </Link>
              </Button>
              {!signedIn && (
                <Button asChild variant="glass" size="lg">
                  <a href={googleSignInUrl('/wish')}>
                    <GoogleLogo />
                    {t('continueWithGoogle')}
                  </a>
                </Button>
              )}
            </>
          }
        />
        <Manifesto />
        {offers.length > 0 && (
          <PopularTrips>
            {offers.map((offer, index) => (
              <TripCard
                key={offer.id}
                image={destinationPhoto(offer)}
                imageAlt={offer.title}
                place={`${localizeCountry(i18n.language, offer.country)} · ${offer.city}`}
                title={offer.title}
                copy={offer.description}
                badge={String(index + 1).padStart(2, '0')}
                renderLink={(content) => (
                  // A visitor signs in first, then lands on the offer (the _authenticated guard).
                  <Link to="/offers/$offerId" params={{ offerId: offer.id }} className="block text-ink no-underline">
                    {content}
                  </Link>
                )}
              />
            ))}
          </PopularTrips>
        )}
        <Method />
        <Reviews />
        <Advisors />
        <Closing
          action={
            <Button asChild variant="ink" size="lg">
              <Link to="/wish">
                {t('closing.start')} <span aria-hidden="true">↗</span>
              </Link>
            </Button>
          }
        />
      </main>
      <SiteFooter />
    </>
  )
}
