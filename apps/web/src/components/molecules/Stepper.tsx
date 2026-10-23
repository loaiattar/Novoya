type Props = {
  value: number
  min: number
  max: number
  onChange: (value: number) => void
  /** The buttons' labels for screen readers ("One traveller fewer"). */
  decreaseLabel: string
  increaseLabel: string
  /** The value in words ("2 travellers"). */
  valueText: string
  id?: string
  describedBy?: string
}

/** A number changed with − and + buttons. */
export function Stepper({ value, min, max, onChange, decreaseLabel, increaseLabel, valueText, id, describedBy }: Props) {
  // aria-disabled, not disabled: a disabled button drops the focus to the top of the page.
  const button = 'size-11 bg-ivory text-lg aria-disabled:cursor-default aria-disabled:opacity-40'
  return (
    <div
      id={id}
      role="group"
      aria-describedby={describedBy}
      className="flex items-center justify-between border border-line bg-white p-2"
    >
      <button
        type="button"
        className={button}
        aria-label={decreaseLabel}
        aria-disabled={value <= min}
        onClick={() => value > min && onChange(value - 1)}
      >
        −
      </button>
      <output aria-live="polite">{valueText}</output>
      <button
        type="button"
        className={button}
        aria-label={increaseLabel}
        aria-disabled={value >= max}
        onClick={() => value < max && onChange(value + 1)}
      >
        +
      </button>
    </div>
  )
}
