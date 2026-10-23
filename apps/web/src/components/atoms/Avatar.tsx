import { initials } from '@/lib/initials'
import { cn } from '@/lib/utils'

export function Avatar({ name, className }: { name: string; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn('grid size-[34px] shrink-0 place-items-center rounded-full bg-sand text-xs font-semibold', className)}
    >
      {initials(name)}
    </span>
  )
}
