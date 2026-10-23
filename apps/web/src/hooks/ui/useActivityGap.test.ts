import { fireEvent, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useActivityGap } from './useActivityGap'

const GAP = 3 * 60_000

describe('useActivityGap', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date('2026-10-19T10:00:00Z'))
  })
  afterEach(() => vi.useRealTimers())

  it('does nothing while the user keeps acting', () => {
    const onReturn = vi.fn()
    renderHook(() => useActivityGap(GAP, onReturn))

    for (let minute = 0; minute < 10; minute++) {
      vi.advanceTimersByTime(2 * 60_000)
      fireEvent.pointerMove(window)
    }

    expect(onReturn).not.toHaveBeenCalled()
  })

  it('calls back once when the user acts after the gap', () => {
    const onReturn = vi.fn()
    renderHook(() => useActivityGap(GAP, onReturn))

    vi.advanceTimersByTime(GAP)
    fireEvent.keyDown(window)
    fireEvent.keyDown(window)

    expect(onReturn).toHaveBeenCalledTimes(1)
  })

  it('stops listening once unmounted', () => {
    const onReturn = vi.fn()
    const { unmount } = renderHook(() => useActivityGap(GAP, onReturn))
    unmount()

    vi.advanceTimersByTime(GAP)
    fireEvent.pointerDown(window)

    expect(onReturn).not.toHaveBeenCalled()
  })
})
