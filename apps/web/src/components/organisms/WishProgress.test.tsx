import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { WishProgress } from './WishProgress'

const STEPS = ['Reading your wish', 'Finding destinations', 'Preparing your preferences']

beforeEach(() => {
  vi.useFakeTimers()
})
afterEach(() => {
  vi.useRealTimers()
})

describe('WishProgress', () => {
  it('mounts the status empty, then announces the first step on the next tick', () => {
    render(<WishProgress steps={STEPS} everyMs={3000} />)
    expect(screen.getByRole('status')).toBeEmptyDOMElement()

    act(() => vi.advanceTimersByTime(0))
    expect(screen.getByRole('status')).toHaveTextContent('Reading your wish')
  })

  it('moves to the next step as time goes', () => {
    render(<WishProgress steps={STEPS} everyMs={3000} />)

    act(() => vi.advanceTimersByTime(3000))
    expect(screen.getByRole('status')).toHaveTextContent('Finding destinations')

    act(() => vi.advanceTimersByTime(3000))
    expect(screen.getByRole('status')).toHaveTextContent('Preparing your preferences')
  })

  it('waits on the last step instead of starting over', () => {
    render(<WishProgress steps={STEPS} everyMs={3000} />)

    act(() => vi.advanceTimersByTime(60_000))

    expect(screen.getByRole('status')).toHaveTextContent('Preparing your preferences')
    expect(vi.getTimerCount()).toBe(0)
  })

  it('stops its timer when it goes away', () => {
    const { unmount } = render(<WishProgress steps={STEPS} everyMs={3000} />)

    unmount()

    expect(vi.getTimerCount()).toBe(0)
  })

  it('keeps an empty status in place while it is not running, and starts over when it runs again', () => {
    const { rerender } = render(<WishProgress steps={STEPS} everyMs={3000} active={false} />)
    expect(screen.getByRole('status')).toBeEmptyDOMElement()
    expect(vi.getTimerCount()).toBe(0)

    rerender(<WishProgress steps={STEPS} everyMs={3000} active />)
    act(() => vi.advanceTimersByTime(3000))
    expect(screen.getByRole('status')).toHaveTextContent('Finding destinations')

    rerender(<WishProgress steps={STEPS} everyMs={3000} active={false} />)
    expect(screen.getByRole('status')).toBeEmptyDOMElement()
    rerender(<WishProgress steps={STEPS} everyMs={3000} active />)
    act(() => vi.advanceTimersByTime(0))
    expect(screen.getByRole('status')).toHaveTextContent('Reading your wish')
  })

  it('reads the note with the step', () => {
    render(<WishProgress steps={STEPS} everyMs={3000} note="This can take up to a minute." />)
    act(() => vi.advanceTimersByTime(0))
    const note = screen.getByText('This can take up to a minute.')
    expect(screen.getByRole('status')).toHaveAttribute('aria-atomic', 'false')

    act(() => vi.advanceTimersByTime(3000))
    // The same node: only the step text changes, so the note is not read again at every step.
    expect(screen.getByText('This can take up to a minute.')).toBe(note)

    expect(screen.getByRole('status')).toHaveTextContent('Finding destinations')
    expect(screen.getByRole('status')).toHaveTextContent('This can take up to a minute.')
  })

  it('keeps turning while the work runs, and only when the device allows motion', () => {
    const { container } = render(<WishProgress steps={STEPS} everyMs={3000} />)
    act(() => vi.advanceTimersByTime(0))

    const animated = [...container.querySelectorAll('[class*="animate-"]')]
    expect(animated.length).toBeGreaterThan(0)
    for (const element of animated) {
      for (const name of element.classList) {
        // A loader that stopped would make the page look stuck during the last, longest step.
        if (name.includes('animate-')) expect(name).toBe('motion-safe:animate-spin')
      }
    }
  })
})
