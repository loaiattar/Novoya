import { useId } from 'react'
import { useTranslation } from 'react-i18next'

import { Input } from '../atoms/Input'

type Props<S extends string> = {
  search: string
  onSearch: (value: string) => void
  status: S | ''
  statuses: readonly S[]
  /** The label of each status, already translated. */
  statusLabel: (status: S) => string
  onStatus: (value: S | '') => void
}

/** The search by client or destination and the status filter above an activity list. */
export function ActivityFilters<S extends string>({ search, onSearch, status, statuses, statusLabel, onStatus }: Props<S>) {
  const id = useId()
  const { t } = useTranslation('admin')
  return (
    <div className="mt-8 mb-4 flex flex-col gap-2.5 md:flex-row">
      <label className="sr-only" htmlFor={`${id}-search`}>
        {t('activity.searchLabel')}
      </label>
      <Input
        id={`${id}-search`}
        type="search"
        value={search}
        onChange={(event) => onSearch(event.target.value)}
        placeholder={t('activity.searchPlaceholder')}
        className="md:max-w-[350px]"
      />
      <label className="sr-only" htmlFor={`${id}-status`}>
        {t('activity.statusFilter')}
      </label>
      <select
        id={`${id}-status`}
        value={status}
        onChange={(event) => onStatus(event.target.value as S | '')}
        className="min-h-11 border border-line bg-white px-3"
      >
        <option value="">{t('activity.allStatuses')}</option>
        {statuses.map((value) => (
          <option key={value} value={value}>
            {statusLabel(value)}
          </option>
        ))}
      </select>
    </div>
  )
}
