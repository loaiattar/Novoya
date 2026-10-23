import { createFileRoute, Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { useMyTrips } from '../../api/trips'
import { Button } from '../../components/atoms/Button'
import { Eyebrow } from '../../components/atoms/Eyebrow'
import { lineTabList, lineTabPanel, lineTabTrigger } from '../../components/molecules/lineTabs'
import { PreferencesTab } from '../../components/organisms/PreferencesTab'
import { ProfileTab } from '../../components/organisms/ProfileTab'
import { TripList } from '../../components/organisms/TripList'
import { AppShell } from '../../components/templates/AppShell'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs'

export const Route = createFileRoute('/_authenticated/trips')({
  component: TripsPage,
})

function TripsPage() {
  const { t } = useTranslation('trips')
  const { trips } = useMyTrips('/trips')

  return (
    <AppShell>
      <main className="pb-22">
        <section className="relative px-5 pt-14 pb-12 md:px-[8vw] md:pt-20">
          <Eyebrow>{t('eyebrow')}</Eyebrow>
          <h1 className="mb-3 text-display-l">{t('title')}</h1>
          <p className="text-muted">{t('intro')}</p>
          <Button asChild className="mt-6 lg:absolute lg:right-[8vw] lg:bottom-15 lg:mt-0">
            <Link to="/wish">{t('newWish')}</Link>
          </Button>
        </section>
        <Tabs defaultValue="trips">
          <TabsList className={`${lineTabList} gap-7.5 px-5 md:px-[8vw]`}>
            <TabsTrigger value="trips" className={lineTabTrigger}>
              {t('tabs.trips')}
              {trips.data && <span className="ml-1.5 rounded-full bg-coral px-1.5 text-xs">{trips.data.length}</span>}
            </TabsTrigger>
            <TabsTrigger value="profile" className={lineTabTrigger}>
              {t('tabs.profile')}
            </TabsTrigger>
            <TabsTrigger value="preferences" className={lineTabTrigger}>
              {t('tabs.preferences')}
            </TabsTrigger>
          </TabsList>
          <TabsContent value="trips" className={`${lineTabPanel} px-5 py-6 md:px-[8vw] md:py-9`}>
            {trips.isPending ? (
              <p role="status" className="text-muted">
                {t('loading')}
              </p>
            ) : trips.isError ? (
              <div className="grid justify-items-start gap-4">
                <p role="alert" className="text-muted">
                  {t('error')}
                </p>
                <Button type="button" onClick={() => void trips.refetch()}>
                  {t('retry')}
                </Button>
              </div>
            ) : trips.data.length === 0 ? (
              <div className="grid justify-items-start gap-4">
                <p className="text-muted">{t('empty')}</p>
                <Button asChild>
                  <Link to="/wish">{t('emptyCta')}</Link>
                </Button>
              </div>
            ) : (
              <TripList trips={trips.data} />
            )}
          </TabsContent>
          <TabsContent value="profile" className={`${lineTabPanel} px-5 py-9 md:px-[8vw]`}>
            <ProfileTab />
          </TabsContent>
          <TabsContent value="preferences" className={`${lineTabPanel} px-5 py-9 md:px-[8vw]`}>
            <PreferencesTab />
          </TabsContent>
        </Tabs>
      </main>
    </AppShell>
  )
}
