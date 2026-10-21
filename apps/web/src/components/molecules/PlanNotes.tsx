import { useTranslation } from 'react-i18next'
type Props = {
    /** False when the client picked no tag. */
    basedOnPreferences: boolean
  }
  export function PlanNotes({ basedOnPreferences }: Props) {
    const { t } = useTranslation('plan')
    return (
      <aside className="grid gap-3 px-5 py-8 text-sm text-muted md:px-[14vw]">
        <p className="m-0">{t('notes.quote')}</p>
        {!basedOnPreferences && <p className="m-0">{t('notes.noPreferences')}</p>}
      </aside>
    )
    }