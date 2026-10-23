import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { PlanBuilding } from './PlanBuilding'

describe('PlanBuilding', () => {
  it('keeps the circle turning while the plan is built, and only when the device allows motion', () => {
    const { container } = render(<PlanBuilding />)

    // Up to a minute: a circle that stopped would make the page look stuck.
    const spinners = [...container.querySelectorAll('[class*="animate-spin"]')]
    expect(spinners.length).toBeGreaterThan(0)
    for (const element of spinners) {
      expect([...element.classList].filter((name) => name.includes('animate-spin'))).toEqual([
        'motion-safe:animate-spin-slow',
      ])
    }
  })
})
