import { useEffect, useRef } from 'react'

const EVENTS = ['pointermove', 'pointerdown', 'keydown', 'wheel', 'touchstart'] as const

/**
 * Calls `onReturn` when the user acts on the page again after `gapMs` without any action.
 * It compares timestamps instead of running a timer, because browsers slow down or pause
 * the timers of background tabs.
 */
export function useActivityGap(gapMs: number, onReturn: () => void) {
  const onReturnRef = useRef(onReturn)
  useEffect(() => {
    onReturnRef.current = onReturn
  })

  useEffect(() => {
    let last = Date.now()
    const onActivity = () => {
      const now = Date.now()
      if (now - last >= gapMs) onReturnRef.current()
      last = now
    }
    for (const event of EVENTS) window.addEventListener(event, onActivity, { passive: true })
    return () => {
      for (const event of EVENTS) window.removeEventListener(event, onActivity)
    }
  }, [gapMs])
}
