import { useQuery } from '@tanstack/react-query'

import { getDbHealthOptions, getHealthOptions } from '../api/generated/@tanstack/react-query.gen'

/** Shows whether the API and its database answer. Useful to check the M0 setup. */
export function ApiStatus() {
  const api = useQuery(getHealthOptions())
  const db = useQuery(getDbHealthOptions())

  return (
    <ul className="api-status" aria-label="Service status">
      <StatusRow label="API" ok={api.data?.status === 'ok'} pending={api.isPending} />
      <StatusRow label="Database" ok={db.data?.status === 'ok'} pending={db.isPending} />
    </ul>
  )
}

function StatusRow({ label, ok, pending }: { label: string; ok: boolean; pending: boolean }) {
  const text = pending ? 'checking…' : ok ? 'ok' : 'unreachable'
  return (
    <li data-state={pending ? 'pending' : ok ? 'ok' : 'error'}>
      {label}: {text}
    </li>
  )
}
