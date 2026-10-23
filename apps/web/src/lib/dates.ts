/** A day as YYYY-MM-DD in the user's own time zone (toISOString would use UTC and can be a day off). */
export function localIsoDate(date = new Date()): string {
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
}
