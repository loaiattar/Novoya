import { rateLimitMessage } from '../rateLimit/wait'

type Tag = { id: string; preselected: boolean }
type Section = { id: string; multi: boolean; tags: Tag[] }

/** The most tags the API takes in one answer (AnswerPanelRequest.selected_tags). */
export const MAX_SELECTED_TAGS = 100

/** The tags picked in each section, by id. */
export type Selection = Record<string, string[]>

/**
 * What the panel picks for the client before they touch it. One tag at most in a single-choice
 * section, and MAX_SELECTED_TAGS at most in all.
 */
export function initialSelection(sections: Section[]): Selection {
  const selection: Selection = {}
  let room = MAX_SELECTED_TAGS
  for (const section of sections) {
    const picked = section.tags.filter((tag) => tag.preselected).map((tag) => tag.id)
    selection[section.id] = (section.multi ? picked : picked.slice(0, 1)).slice(0, room)
    room -= selection[section.id].length
  }
  return selection
}

/**
 * Picks or unpicks a tag. In a single-choice section, picking a tag replaces the previous one.
 * A pick that would go over MAX_SELECTED_TAGS leaves the selection as it was; unpicking always
 * works.
 */
export function toggleTag(selection: Selection, section: Section, tagId: string): Selection {
  const current = selection[section.id] ?? []
  const next = current.includes(tagId)
    ? current.filter((id) => id !== tagId)
    : section.multi
      ? [...current, tagId]
      : [tagId]
  const changed = { ...selection, [section.id]: next }
  const adds = next.length > current.length
  return adds && selectedTags(changed).length > MAX_SELECTED_TAGS ? selection : changed
}

/** The selection as the API takes it. */
export function selectedTags(selection: Selection): { section: string; tag: string }[] {
  return Object.entries(selection).flatMap(([section, tags]) => tags.map((tag) => ({ section, tag })))
}

export type AnswerPanelErrorKey =
  | 'answers.invalid'
  | 'answers.wishNotFound'
  | 'answers.alreadyAnswered'
  | 'answers.noOfferFits'
  | 'answers.tooManyRequests'
  | 'answers.planFailed'
  | 'answers.connectionLost'
  | 'answers.inProgress'
  | 'answers.unknown'

type AnswerPanelMessageKey = AnswerPanelErrorKey | 'rateLimit.waitSeconds' | 'rateLimit.waitMinutes'

/**
 * The key of the message for panel answers that failed (errors.json). `status` is undefined
 * when no response came back (network failure). Then, as on a gateway timeout (504), the API
 * may still finish and save the plan: the message must not promise that nothing happened.
 * Any other server error rolled the answers back: the client can simply send again.
 */
export function answerPanelErrorKey(code: string | undefined, status: number | undefined): AnswerPanelErrorKey {
  if (status === undefined || status === 504) return 'answers.connectionLost'
  if (status >= 500) return 'answers.planFailed'
  switch (code) {
    case 'invalid_answers':
    case 'invalid_input':
      return 'answers.invalid'
    case 'wish_not_found':
      return 'answers.wishNotFound'
    case 'answer_in_progress':
      return 'answers.inProgress'
    case 'invalid_transition':
    case 'conflict':
      return 'answers.alreadyAnswered'
    case 'no_offer_fits':
      return 'answers.noOfferFits'
    case 'too_many_requests':
      return 'answers.tooManyRequests'
    default:
      return 'answers.unknown'
  }
}

/** The message for failed panel answers, with a wait when Retry-After is present. */
export function answerPanelError(
  code: string | undefined,
  status: number | undefined,
  retryAfterSeconds?: number,
): { key: AnswerPanelMessageKey; count?: number } {
  const key = answerPanelErrorKey(code, status)
  return key === 'answers.tooManyRequests' ? rateLimitMessage(key, retryAfterSeconds) : { key }
}
