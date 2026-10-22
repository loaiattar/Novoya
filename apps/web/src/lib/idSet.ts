// Sets of row ids for the admin tables whose switches save one row at a time: the rows that
// wait and the rows that failed. New sets, so React sees the change.

export function withId(ids: ReadonlySet<string>, id: string): ReadonlySet<string> {
  return new Set(ids).add(id)
}

export function withoutId(ids: ReadonlySet<string>, id: string): ReadonlySet<string> {
  const next = new Set(ids)
  next.delete(id)
  return next
}
