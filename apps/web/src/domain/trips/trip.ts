import type { Trip } from '../../api/generated/types.gen'

export type TripFacts = Pick<Trip, 'wish_id' | 'status' | 'plan_id' | 'plan_status' | 'quote_id'>

/** The page a trip opens: its quote, else its plan, else its preference panel, else the wish page. */
export type TripTarget =
  | { kind: 'quote'; quoteId: string }
  | { kind: 'plan'; planId: string }
  | { kind: 'panel'; wishId: string }
  | { kind: 'wish' }

export function tripTarget(trip: TripFacts): TripTarget {
  if (trip.quote_id) return { kind: 'quote', quoteId: trip.quote_id }
  if (trip.plan_id) return { kind: 'plan', planId: trip.plan_id }
  if (trip.status === 'panel_shown') return { kind: 'panel', wishId: trip.wish_id }
  return { kind: 'wish' }
}

/** Where the trip stands, for the client: the plan's status when there is a plan, else the wish's. */
export type TripStatus =
  | 'draft'
  | 'not_covered'
  | 'panel_shown'
  | 'answered'
  | 'plan_proposed'
  | 'sent'
  | 'in_progress'
  | 'quoted'
  | 'accepted'
  | 'rejected'

export function tripStatus(trip: Pick<Trip, 'status' | 'plan_status'>): TripStatus {
  switch (trip.plan_status) {
    case 'proposed':
      return 'plan_proposed'
    case 'requested':
      return 'sent'
    case 'negotiating':
      return 'in_progress'
    case 'quoted':
      return 'quoted'
    case 'accepted':
      return 'accepted'
    case 'rejected':
      return 'rejected'
    default:
      return trip.status === 'planned' ? 'answered' : trip.status
  }
}
