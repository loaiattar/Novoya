// Classes for shadcn Tabs drawn as the mockup's underlined tabs.

export const lineTabList =
  'flex h-auto min-h-11 w-full justify-start overflow-x-auto rounded-none border-b border-line bg-transparent p-0'

export const lineTabTrigger =
  'h-auto min-h-11 flex-none rounded-none border-0 border-b-2 border-transparent bg-transparent text-sm text-muted shadow-none hover:text-ink data-[state=active]:border-ink data-[state=active]:bg-transparent data-[state=active]:text-ink data-[state=active]:shadow-none'

/** The panel is focusable (Radix): show where focus is. */
export const lineTabPanel = 'focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ink focus-visible:outline-solid'
