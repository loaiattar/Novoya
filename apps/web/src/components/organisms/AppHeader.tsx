import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { canOpen, type Role } from '../../domain/auth/roles'
import { Avatar } from '../atoms/Avatar'
import { HomeLink } from '../molecules/HomeLink'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../ui/dropdown-menu'
import { LanguageChoice } from './LanguageChoice'

type Props = {
  /** The signed-in user's name. Without it, the header shows only the brand. */
  userName?: string
  role?: Role
  onSignOut?: () => void
  signingOut?: boolean
  /** Shown when signing out failed: the user is still signed in. */
  signOutError?: string
}

const navLink =
  'relative py-2 text-sm text-ink no-underline after:absolute after:inset-x-0 after:-bottom-[25px] after:h-0.5 data-[status=active]:after:bg-coral'

/** The header of every signed-in page: brand, main links and the account menu. */
export function AppHeader({ userName, role = 'client', onSignOut, signingOut = false, signOutError }: Props) {
  const { t } = useTranslation('header')
  return (
    <header className="fixed inset-x-0 top-0 z-20 border-b border-line bg-paper/90 backdrop-blur-md">
      <div className="flex h-18 items-center justify-between px-5 md:h-22 md:px-[5vw]">
        <HomeLink />
        {userName && (
          <>
            <nav aria-label={t('mainNav')} className="hidden items-center gap-7 lg:flex">
              <Link to="/wish" className={navLink}>
                {t('compose')}
              </Link>
              <Link to="/trips" className={navLink}>
                {t('myTrips')}
              </Link>
              {canOpen(role, 'agent') && (
                <Link to="/agent" className={navLink}>
                  {t('agencySpace')}
                </Link>
              )}
              {canOpen(role, 'admin') && (
                <Link to="/admin" className={navLink}>
                  {t('administration')}
                </Link>
              )}
            </nav>
            <div className="flex items-center gap-4 md:gap-6">
              <LanguageChoice />
              <DropdownMenu>
                <DropdownMenuTrigger className="flex min-h-11 items-center gap-2.5 rounded-full text-sm">
                  <Avatar name={userName} />
                  <span className="hidden max-w-48 truncate lg:inline">{userName}</span>
                  <span aria-hidden="true">⌄</span>
                  <span className="sr-only lg:hidden">{t('accountMenu')}</span>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-52 rounded-none border-0 p-2.5 shadow-menu">
                  {/* Below lg the nav is hidden, so its links live here. */}
                  <div className="lg:hidden">
                    <DropdownMenuItem asChild>
                      <Link to="/wish">{t('compose')}</Link>
                    </DropdownMenuItem>
                    <DropdownMenuItem asChild>
                      <Link to="/trips">{t('myTrips')}</Link>
                    </DropdownMenuItem>
                    {canOpen(role, 'agent') && (
                      <DropdownMenuItem asChild>
                        <Link to="/agent">{t('agencySpace')}</Link>
                      </DropdownMenuItem>
                    )}
                    {canOpen(role, 'admin') && (
                      <DropdownMenuItem asChild>
                        <Link to="/admin">{t('administration')}</Link>
                      </DropdownMenuItem>
                    )}
                    <DropdownMenuSeparator />
                  </div>
                  <DropdownMenuItem asChild>
                    <Link to="/settings">{t('settings')}</Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem disabled={signingOut} onSelect={onSignOut}>
                    {signingOut ? t('signingOut') : t('signOut')}
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </>
        )}
      </div>
      {signOutError && (
        <p role="alert" className="bg-white px-5 py-2 text-right text-sm text-danger md:px-[5vw]">
          {signOutError}
        </p>
      )}
    </header>
  )
}
