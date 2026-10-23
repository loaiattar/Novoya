import type { ReactNode } from 'react'

import { Chip } from '../atoms/Chip'

type Props = {
  /** "3 preferences". */
  summary: string
  chips: string[]
  action: ReactNode
}

/** The bar stuck to the bottom of the preferences panel, with the main action. */
export function StickyAction({ summary, chips, action }: Props) {
  return (
    <div className="fixed right-0 bottom-0 z-10 flex w-full items-center justify-between border-t border-line bg-white px-4 py-[13px] md:w-[67%] md:px-[4vw] md:py-[18px]">
      <div className="hidden items-center gap-3.5 md:flex">
        <span className="text-sm">{summary}</span>
        <div className="flex gap-1.5">
          {chips.map((chip) => (
            <Chip key={chip}>{chip}</Chip>
          ))}
        </div>
      </div>
      {action}
    </div>
  )
}
