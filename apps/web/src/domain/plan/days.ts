/** The plan's items by day, the days in order, each day's items in the order the API gave. */
export function groupByDay<Item extends { day: number }>(items: Item[]): { day: number; items: Item[] }[] {
  const days = new Map<number, Item[]>()
  for (const item of items) days.set(item.day, [...(days.get(item.day) ?? []), item])
  return [...days.entries()].sort(([a], [b]) => a - b).map(([day, dayItems]) => ({ day, items: dayItems }))
}
