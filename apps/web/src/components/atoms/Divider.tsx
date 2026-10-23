/** A thin line across, with an optional word in the middle ("or with your e-mail"). */
export function Divider({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2.5 text-xs text-muted">
      <span aria-hidden="true" className="h-px flex-1 bg-line" />
      {label}
      {label && <span aria-hidden="true" className="h-px flex-1 bg-line" />}
    </div>
  )
}
