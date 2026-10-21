import { Google } from '@thesvg/react';

type GoogleButtonProps = {
    onClick?: () => void
  }
  
  export function GoogleButton({ onClick }: GoogleButtonProps) {
    return (
      <button
        type="button"
        onClick={onClick}
        className="flex w-full items-center justify-center gap-3 rounded-full border border-line bg-white px-6 py-3.5 text-base text-ink"
      >
        <Google variant="mono" className="h-[18px] w-[18px]" aria-hidden="true" />
        Continuer avec Google
      </button>
    )
  }


  