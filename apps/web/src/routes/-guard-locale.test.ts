import { afterEach, describe, expect, it, vi } from 'vitest'

import i18n from '../i18n'
import { Route } from './_authenticated'

// Rendering the page cannot catch an English first frame: in tests, React runs the root's
// useEffect before the page is looked at. So this calls the guard itself.
describe('/_authenticated guard', () => {
  afterEach(() => vi.restoreAllMocks())

  it("switches to the user's language before the page renders", async () => {
    vi.spyOn(navigator, 'languages', 'get').mockReturnValue(['en-US'])
    const queryClient = { ensureQueryData: async () => ({ locale: 'fr' }) }

    await Route.options.beforeLoad!({ context: { queryClient }, location: { href: '/' } } as never)

    expect(i18n.language).toBe('fr')
  })
})
