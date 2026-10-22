import type { AgentPlan } from '../../api/generated/types.gen'

export type Missing =
  | { kind: 'item'; id: string; day: number; title: string | null }
  | { kind: 'extra'; id: string; label: string }

/**
 * The lines that still keep the quote from going out, items first, then extras. The same
 * rule as the API's Plan.ready_to_quote (planning/domain/plan.py): every kept item and every
 * on_quote extra has a price, and every supplement that needs a quantity check is confirmed.
 * The API's ready_to_quote decides; this list only says why.
 */
export function missingPrices(plan: AgentPlan): Missing[] {
  const items: Missing[] = plan.items
    .filter((item) => !item.removed && item.negotiated_price === null)
    .map((item) => ({ kind: 'item', id: item.id, day: item.day, title: item.title }))
  const extras: Missing[] = plan.extras
    .filter(
      (extra) =>
        (extra.pricing === 'on_quote' && extra.price_eur === null) || (extra.needs_quantity_check && !extra.confirmed),
    )
    .map((extra) => ({ kind: 'extra', id: extra.extra_id, label: extra.label }))
  return [...items, ...extras]
}
