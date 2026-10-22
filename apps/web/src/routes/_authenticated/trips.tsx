import { createFileRoute, Link } from '@tanstack/react-router'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '../../components/atoms/Button'
import { Eyebrow } from '../../components/atoms/Eyebrow'
import { lineTabList, lineTabPanel, lineTabTrigger } from '../../components/molecules/lineTabs'
import { HistoryPanel } from '../../components/organisms/HistoryPanel'
import { ThreadList } from '../../components/organisms/ThreadList'
import { AppShell } from '../../components/templates/AppShell'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs'
import { DemoBanner } from '../../components/molecules/DemoBanner'
import { listThreads } from '../../fixtures/trips'

export const Route = createFileRoute('/_authenticated/trips')({
  component: TripsPage,
})

function TripsPage() {
  const { t } = useTranslation('trips')
  const threads = listThreads()
  const [selectedId, setSelectedId] = useState(threads[0]?.id)
  const selected = threads.find((thread) => thread.id === selectedId) ?? threads[0]

  return (
    <AppShell>
      <DemoBanner />
      <main className="pb-22">
        <section className="relative px-5 pt-14 pb-12 md:px-[8vw] md:pt-20">
          <Eyebrow>{t('eyebrow')}</Eyebrow>
          <h1 className="mb-3 text-[55px] leading-none md:text-[75px]">{t('title')}</h1>
          <p className="text-muted">{t('intro')}</p>
          <Button asChild className="mt-6 lg:absolute lg:right-[8vw] lg:bottom-15 lg:mt-0">
            <Link to="/wish">{t('newWish')}</Link>
          </Button>
        </section>
        <Tabs defaultValue="trips">
          <TabsList className={`${lineTabList} gap-7.5 px-5 md:px-[8vw]`}>
            <TabsTrigger value="trips" className={lineTabTrigger}>
              {t('tabs.trips')}
              <span className="ml-1.5 rounded-full bg-coral px-1.5 text-xs">{threads.length}</span>
            </TabsTrigger>
            <TabsTrigger value="profile" className={lineTabTrigger}>
              {t('tabs.profile')}
            </TabsTrigger>
            <TabsTrigger value="preferences" className={lineTabTrigger}>
              {t('tabs.preferences')}
            </TabsTrigger>
          </TabsList>
          <TabsContent value="trips" className={`${lineTabPanel} px-5 py-6 md:px-[8vw] md:py-9 lg:grid lg:grid-cols-[0.9fr_1.1fr] lg:gap-7.5`}>
            {selected ? (
              <>
                <ThreadList threads={threads} selectedId={selected.id} onSelect={setSelectedId} />
                <HistoryPanel
                  key={selected.id}
                  title={selected.title}
                  version={selected.version}
                  planId={selected.planId}
                />
              </>
            ) : (
              <p className="text-muted lg:col-span-2">{t('empty')}</p>
            )}
          </TabsContent>
          <TabsContent value="profile" className={`${lineTabPanel} px-5 py-9 text-muted md:px-[8vw]`}>
            {t('soon.profile')}
          </TabsContent>
          <TabsContent value="preferences" className={`${lineTabPanel} px-5 py-9 text-muted md:px-[8vw]`}>
            {t('soon.preferences')}
          </TabsContent>
        </Tabs>
      </main>
    </AppShell>
  )
}
