import { cva, type VariantProps } from 'class-variance-authority'
import { Slot } from 'radix-ui'
import type { ButtonHTMLAttributes, Ref } from 'react'

import { cn } from '@/lib/utils'

const buttonVariants = cva(
  // Only the lift and the colours move: the focus ring (index.css) must show at once.
  'inline-flex items-center justify-center gap-4 rounded-full font-semibold text-sm no-underline transition-[translate,background-color,color] duration-250 hover:-translate-y-0.5 disabled:pointer-events-none disabled:opacity-60',
  {
    variants: {
      variant: {
        coral: 'bg-coral text-ink hover:bg-coral-light',
        ink: 'bg-ink text-white',
        // On photos and the dark sections.
        glass: 'border border-white/45 bg-white/10 text-white backdrop-blur-md',
        outline: 'border border-line bg-white text-ink',
        // Underlined text, for secondary actions.
        link: 'rounded-none p-0 font-normal underline underline-offset-4 hover:translate-y-0',
      },
      size: {
        md: 'min-h-11 px-5 py-3',
        lg: 'min-h-14 px-6 py-4',
        inline: '',
      },
    },
    compoundVariants: [{ variant: 'link', className: 'min-h-0 px-0 py-0' }],
    defaultVariants: { variant: 'ink', size: 'md' },
  },
)

type Props = ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonVariants> & {
    /** Render the child (a router `Link`, an `<a>`) with the button's look. */
    asChild?: boolean
    ref?: Ref<HTMLButtonElement>
  }

export function Button({ variant, size, asChild = false, className, ...props }: Props) {
  const Component = asChild ? Slot.Root : 'button'
  return (
    <Component
      {...(asChild ? {} : { type: 'button' as const })}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  )
}
