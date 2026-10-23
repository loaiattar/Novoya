import { useTranslation } from 'react-i18next'

import { type SectionTone, TONE_CLASSES } from '../../domain/panel/sectionTone'
import { TagToggle } from './TagToggle'

type Props = {
  title: string
  /** Several tags can be picked; otherwise one at most. */
  multi: boolean
  tags: { id: string; label: string }[]
  selected: string[]
  onToggle: (tagId: string) => void
  /** The section's colour, from sectionTones(): the same as on the Preferences tab. The
   * catalog sections never share a colour; every other section has tone 8, which no catalog
   * section uses, so those other sections can only match each other. */
  tone?: SectionTone
}

/** One section of the preferences panel: a title and its tags. */
export function TagGroup({ title, multi, tags, selected, onToggle, tone }: Props) {
  const { t } = useTranslation('preferences')
  return (
    <fieldset data-tone={tone} className="m-0 border-0 border-t border-line px-0 py-[25px]">
      <legend
        className={`float-left mb-4 w-full p-0 font-serif text-lg ${tone ? `border-l-4 pl-3 ${TONE_CLASSES[tone].accent}` : ''}`}
      >
        {title}
        {!multi && <span className="ml-2 font-sans text-xs text-muted">{t('singleChoice')}</span>}
      </legend>
      <div className="clear-both flex flex-wrap gap-2.5">
        {tags.map((tag) => (
          <TagToggle
            key={tag.id}
            label={tag.label}
            selected={selected.includes(tag.id)}
            onToggle={() => onToggle(tag.id)}
          />
        ))}
      </div>
    </fieldset>
  )
}
