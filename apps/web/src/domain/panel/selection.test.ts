import { describe, expect, it } from 'vitest'

import {
  answerPanelError,
  answerPanelErrorKey,
  initialSelection,
  MAX_SELECTED_TAGS,
  selectedTags,
  toggleTag,
} from './selection'

const mood = {
  id: 'mood',
  multi: true,
  tags: [
    { id: 'calm', preselected: true },
    { id: 'sea', preselected: true },
    { id: 'culture', preselected: false },
  ],
}
const pace = {
  id: 'pace',
  multi: false,
  tags: [
    { id: 'slow', preselected: true },
    { id: 'busy', preselected: true },
  ],
}

describe('initialSelection', () => {
  it('picks the preselected tags, one at most in a single-choice section', () => {
    expect(initialSelection([mood, pace])).toEqual({ mood: ['calm', 'sea'], pace: ['slow'] })
  })

  it(`picks ${MAX_SELECTED_TAGS} preselected tags at most in all`, () => {
    const big = (id: string) => ({
      id,
      multi: true,
      tags: Array.from({ length: 30 }, (_, i) => ({ id: `${id}-${i}`, preselected: true })),
    })
    const selection = initialSelection([big('a'), big('b'), big('c'), big('d'), pace])
    expect(selectedTags(selection)).toHaveLength(MAX_SELECTED_TAGS)
    expect(selection.d).toHaveLength(10)
    expect(selection.pace).toEqual([])
  })
})

describe('toggleTag', () => {
  it('adds and removes a tag in a multiple-choice section', () => {
    const added = toggleTag({ mood: ['calm'] }, mood, 'culture')
    expect(added.mood).toEqual(['calm', 'culture'])
    expect(toggleTag(added, mood, 'calm').mood).toEqual(['culture'])
  })

  it('replaces the tag in a single-choice section, and can clear it', () => {
    const replaced = toggleTag({ pace: ['slow'] }, pace, 'busy')
    expect(replaced.pace).toEqual(['busy'])
    expect(toggleTag(replaced, pace, 'busy').pace).toEqual([])
  })

  it('does not change the selection it was given', () => {
    const before = { mood: ['calm'] }
    toggleTag(before, mood, 'sea')
    expect(before).toEqual({ mood: ['calm'] })
  })
})

describe(`toggleTag at the limit of ${MAX_SELECTED_TAGS} tags`, () => {
  // Tags picked in other sections, to bring the selection near the limit.
  const others = (count: number) => Array.from({ length: count }, (_, i) => `tag-${i}`)

  it('adds tags up to the limit', () => {
    const added = toggleTag({ others: others(98), mood: ['calm'] }, mood, 'sea')
    expect(selectedTags(added)).toHaveLength(MAX_SELECTED_TAGS)
  })

  it('refuses one more tag in a full multiple-choice section', () => {
    const full = { others: others(99), mood: ['calm'] }
    expect(toggleTag(full, mood, 'sea')).toBe(full)
  })

  it('refuses a first tag in an empty single-choice section', () => {
    const full = { others: others(99), mood: ['calm'], pace: [] }
    expect(toggleTag(full, pace, 'slow')).toBe(full)
  })

  it('still removes a tag, and replaces the tag of a single-choice section', () => {
    const full = { others: others(98), mood: ['calm'], pace: ['slow'] }
    expect(toggleTag(full, mood, 'calm').mood).toEqual([])
    expect(toggleTag(full, pace, 'busy').pace).toEqual(['busy'])
  })

  it('removes and replaces tags in a selection already over the limit', () => {
    const over = { others: others(150), mood: ['calm'], pace: ['slow'] }
    expect(toggleTag(over, mood, 'calm').mood).toEqual([])
    expect(toggleTag(over, pace, 'busy').pace).toEqual(['busy'])
    expect(toggleTag(over, mood, 'sea')).toBe(over)
  })
})

describe('selectedTags', () => {
  it('lists every picked tag with its section', () => {
    expect(selectedTags({ mood: ['calm', 'sea'], pace: [] })).toEqual([
      { section: 'mood', tag: 'calm' },
      { section: 'mood', tag: 'sea' },
    ])
  })
})

describe('answerPanelErrorKey', () => {
  it('explains the API errors, with a fallback', () => {
    expect(answerPanelErrorKey('invalid_answers', 422)).toBe('answers.invalid')
    expect(answerPanelErrorKey('wish_not_found', 404)).toBe('answers.wishNotFound')
    expect(answerPanelErrorKey('invalid_transition', 409)).toBe('answers.alreadyAnswered')
    expect(answerPanelErrorKey('no_offer_fits', 422)).toBe('answers.noOfferFits')
    expect(answerPanelErrorKey('answer_in_progress', 409)).toBe('answers.inProgress')
    expect(answerPanelErrorKey('too_many_requests', 429)).toBe('answers.tooManyRequests')
    expect(answerPanelErrorKey('unknown', 400)).toBe('answers.unknown')
  })

  it('says the plan could not be built on a server error', () => {
    expect(answerPanelErrorKey('unknown', 500)).toBe('answers.planFailed')
    expect(answerPanelErrorKey('unknown', 503)).toBe('answers.planFailed')
  })

  it('says the plan may still be ready when the answer was lost on the way', () => {
    expect(answerPanelErrorKey(undefined, undefined)).toBe('answers.connectionLost')
    expect(answerPanelErrorKey('unknown', 504)).toBe('answers.connectionLost')
  })
})

describe('answerPanelError', () => {
  it('keeps the usual message without Retry-After, and names the wait when it is there', () => {
    expect(answerPanelError('too_many_requests', 429)).toEqual({ key: 'answers.tooManyRequests' })
    expect(answerPanelError('too_many_requests', 429, 12)).toEqual({ key: 'rateLimit.waitSeconds', count: 12 })
    expect(answerPanelError('no_offer_fits', 422, 720)).toEqual({ key: 'answers.noOfferFits' })
  })
})
