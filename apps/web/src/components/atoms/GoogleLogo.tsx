import { cn } from '@/lib/utils'

/** Google's "G", in its four colours, as their sign-in branding asks. Next to a text that names it. */
export function GoogleLogo({ className }: { className?: string }) {
  return <img src="/icons/google.svg" alt="" width={18} height={18} className={cn('size-[18px] shrink-0', className)} />
}
