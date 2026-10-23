/** Up to two initials from a name or an email. */
export function initials(name: string): string {
  const words = name.split(/[\s@._-]+/).filter(Boolean)
  return words
    .slice(0, 2)
    // Array.from splits by code point, so an emoji or other astral character stays whole.
    .map((word) => Array.from(word)[0]!.toUpperCase())
    .join('')
}
