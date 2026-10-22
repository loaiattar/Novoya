/** The brand's "pas de côté": the last `letter` of `text` steps up, in yellow. Text without
 * that letter is shown as it is. Screen readers read the text whole. */
export function Jump({ text, letter = 'o' }: { text: string; letter?: string }) {
  const at = text.lastIndexOf(letter)
  if (at < 0) return text
  return (
    <>
      {text.slice(0, at)}
      <span className="inline-block -translate-y-[0.32em] text-coral">{letter}</span>
      {text.slice(at + 1)}
    </>
  )
}
