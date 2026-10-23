import type { ReactNode } from 'react'

type Props = {
  /** The photo side (AuthMedia). On phones, a band above the form. */
  media: ReactNode
  children: ReactNode
}

/** The account pages: a photo, then the form in a narrow column. */
export function AuthTemplate({ media, children }: Props) {
  return (
    <main className="min-h-screen md:grid md:h-dvh md:grid-cols-[1.05fr_0.95fr] md:overflow-hidden">
      {media}
      <section className="bg-paper px-[22px] py-6 md:min-h-0 md:overflow-y-auto md:px-[30px] md:py-4">
        <div className="mx-auto flex min-h-full max-w-[420px] flex-col justify-center">
          {children}
        </div>
      </section>
    </main>
  )
}
