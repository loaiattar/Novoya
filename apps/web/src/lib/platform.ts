/** True on macOS, iPhone and iPad, where shortcuts use ⌘ instead of Ctrl. */
export function isApplePlatform(): boolean {
  if (typeof navigator === 'undefined') return false
  const platform =
    (navigator as Navigator & { userAgentData?: { platform?: string } }).userAgentData?.platform ??
    navigator.platform ??
    navigator.userAgent
  return /mac|iphone|ipad|ipod/i.test(platform)
}
