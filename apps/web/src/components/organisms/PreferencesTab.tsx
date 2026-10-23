import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { X } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import {
  listMyPreferencesOptions,
  listMyPreferencesQueryKey,
  removeMyPreferenceMutation,
} from '../../api/generated/@tanstack/react-query.gen'
import type { PreferenceSectionOut } from '../../api/generated/types.gen'
import { sectionTones, TONE_CLASSES } from '../../domain/panel/sectionTone'
import { Button } from '../atoms/Button'

/**
 * The Preferences tab of /trips (#165): the tags the client picked on the panels of their
 * wishes, grouped by section with the section's colour (the same as on the panel). A tag
 * can be removed; the API takes it off every answered wish of the client.
 */
export function PreferencesTab() {
  const { t } = useTranslation('preferences')
  const queryClient = useQueryClient()
  const preferences = useQuery(listMyPreferencesOptions())
  const remove = useMutation({
    ...removeMyPreferenceMutation(),
    onSuccess: (_data, { path }) => {
      queryClient.setQueryData<PreferenceSectionOut[]>(listMyPreferencesQueryKey(), (sections) =>
        sections
          ?.map((section) =>
            section.id === path.section
              ? { ...section, tags: section.tags.filter((tag) => tag.id !== path.tag) }
              : section,
          )
          .filter((section) => section.tags.length > 0),
      )
      void queryClient.invalidateQueries({ queryKey: listMyPreferencesQueryKey() })
    },
    // 409 preference_locked: the trip went to the agency meanwhile. Reload, so the tag shows
    // without its button.
    onError: () => void queryClient.invalidateQueries({ queryKey: listMyPreferencesQueryKey() }),
  })

  if (preferences.isPending) return <p className="text-muted">{t('saved.loading')}</p>
  if (preferences.isError) return <p role="alert" className="text-danger">{t('saved.loadFailed')}</p>

  if (preferences.data.length === 0) {
    return (
      <div className="max-w-xl">
        <p className="mb-6 text-muted">{t('saved.empty')}</p>
        <Button asChild variant="coral">
          <Link to="/wish">{t('saved.emptyCta')}</Link>
        </Button>
      </div>
    )
  }

  const tones = sectionTones(preferences.data.map((section) => section.id))

  return (
    <div className="max-w-3xl">
      <p className="mb-6 text-muted">{t('saved.intro')}</p>
      {remove.isError && (
        <p role="alert" className="mb-4 text-danger">
          {t('saved.removeFailed')}
        </p>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        {preferences.data.map((section) => {
          const tone = tones.get(section.id) ?? 1
          const headingId = `preferences-section-${section.id}`
          return (
            <section
              key={section.id}
              aria-labelledby={headingId}
              data-tone={tone}
              className={`rounded-lg border-l-4 p-4 ${TONE_CLASSES[tone].accent} ${TONE_CLASSES[tone].soft}`}
            >
              <h3 id={headingId} className="mb-3 font-serif text-lg">
                {section.title}
              </h3>
              <ul className="flex flex-wrap gap-2">
                {section.tags.map((tag) => (
                  <li
                    key={tag.id}
                    className="flex min-h-11 items-center gap-1 rounded-full border border-line bg-paper py-1 pr-1 pl-4 text-sm text-ink"
                  >
                    {tag.label}
                    {tag.removable ? (
                      <button
                        type="button"
                        aria-label={t('saved.remove', { tag: tag.label })}
                        disabled={remove.isPending}
                        onClick={() => remove.mutate({ path: { section: section.id, tag: tag.id } })}
                        className="grid size-9 place-items-center rounded-full hover:bg-sand disabled:opacity-50"
                      >
                        <X aria-hidden="true" className="size-4" />
                      </button>
                    ) : (
                      <span className="pr-3 pl-1 text-xs text-muted">{t('saved.locked')}</span>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )
        })}
      </div>
    </div>
  )
}
