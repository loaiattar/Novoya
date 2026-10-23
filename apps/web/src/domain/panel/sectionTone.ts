/**
 * The colours of the preference panel sections (#165), on the panel and on the Preferences
 * tab. A section has the same colour on every page:
 * - the catalog sections have fixed tones that never clash: the DÉTOUR import gives
 *   accommodation, transport, activities and style; the seed offers style, rhythm, food,
 *   transport and accommodation; an untagged offer goes to preferences;
 * - any other section (a back-office offer accepts any section:tag, e.g. family or season)
 *   gets OTHER_TONE, which no catalog section uses: it never looks like a catalog section and
 *   is the same on every page; two such sections share that colour.
 * The colours are the theme tokens --color-section-N and --color-section-N-soft (index.css).
 */
export const SECTION_TONES = 8

export type SectionTone = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8

/** The tone of every section outside the catalog. */
export const OTHER_TONE: SectionTone = 8

// A Map, not an object: a section named "constructor" must not reach Object.prototype.
const KNOWN = new Map<string, SectionTone>([
  ['style', 1],
  ['rhythm', 2],
  ['pace', 2],
  ['food', 3],
  ['accommodation', 4],
  ['stay', 4],
  ['activities', 5],
  ['transport', 6],
  ['preferences', 7],
])

const key = (sectionId: string) => sectionId.trim().toLowerCase()

/** The tone of one section, the same on every page. */
export function sectionTone(sectionId: string): SectionTone {
  return KNOWN.get(key(sectionId)) ?? OTHER_TONE
}

/** The tone of each section of a page, keyed by section id. */
export function sectionTones(sectionIds: readonly string[]): Map<string, SectionTone> {
  return new Map(sectionIds.map((id) => [id, sectionTone(id)]))
}

/** Literal class names, so Tailwind finds them. */
export const TONE_CLASSES: Record<SectionTone, { accent: string; soft: string }> = {
  1: { accent: 'border-section-1', soft: 'bg-section-1-soft' },
  2: { accent: 'border-section-2', soft: 'bg-section-2-soft' },
  3: { accent: 'border-section-3', soft: 'bg-section-3-soft' },
  4: { accent: 'border-section-4', soft: 'bg-section-4-soft' },
  5: { accent: 'border-section-5', soft: 'bg-section-5-soft' },
  6: { accent: 'border-section-6', soft: 'bg-section-6-soft' },
  7: { accent: 'border-section-7', soft: 'bg-section-7-soft' },
  8: { accent: 'border-section-8', soft: 'bg-section-8-soft' },
}
