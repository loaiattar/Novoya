import type { ReactNode } from 'react'

const LINK = 'block h-full p-5 hover:bg-paper focus-visible:outline-2 focus-visible:outline-ink'

type Props = {
  label: string
  value: number
  /** Short lines under the number: what it leaves out (hidden, inactive…). */
  details?: string[]
  /** The link around the tile (a router `Link`), given the tile's content and the classes
   * that make the whole tile the target. None: not a link. */
  renderLink?: (content: ReactNode, className: string) => ReactNode
}

/** One key number on the admin home, with its label and what it leaves out. */
export function StatTile({ label, value, details = [], renderLink }: Props) {
  const content = (
    <>
      <span className="block font-serif text-[39px] leading-none">{value}</span>
      <span className="mt-2 block font-semibold">{label}</span>
      {details.map((detail) => (
        <small key={detail} className="mt-1 block text-xs text-muted">
          {detail}
        </small>
      ))}
    </>
  )
  return (
    <li className="border border-line bg-white">
      {renderLink ? renderLink(content, LINK) : <div className="h-full p-5">{content}</div>}
    </li>
  )
}

