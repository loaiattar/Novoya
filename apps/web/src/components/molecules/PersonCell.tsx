type Person = { name: string | null; email: string }

type Props = {
  person: Person | null
  /** Shown instead, for example when the account was deleted. */
  fallback: string
}

/** A client or an agent in an admin table: the name, then the email, as on the users page. */
export function PersonCell({ person, fallback }: Props) {
  if (!person) return <span className="text-muted">{fallback}</span>
  return (
    <span className="grid">
      <b className="font-semibold">{person.name ?? person.email}</b>
      <small className="mt-1 text-xs break-all text-muted">{person.email}</small>
    </span>
  )
}
