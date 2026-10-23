import { useMutation, useQueryClient } from '@tanstack/react-query'
import { createFileRoute, Link, useRouter } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { ApiError } from '../../api/errors'
import { changePasswordMutation, deleteMeMutation } from '../../api/generated/@tanstack/react-query.gen'
import { Eyebrow } from '../../components/atoms/Eyebrow'
import { ChangePasswordForm } from '../../components/organisms/ChangePasswordForm'
import { DeleteAccount } from '../../components/organisms/DeleteAccount'
import { AppShell } from '../../components/templates/AppShell'
import { useAccountErrors } from '../-accountErrors'

export const Route = createFileRoute('/_authenticated/settings')({
  component: SettingsPage,
})

function SettingsPage() {
  const { me } = Route.useRouteContext()
  const { t } = useTranslation('settings')
  const change = useMutation(changePasswordMutation())
  const errors = useAccountErrors(change.error)
  const hasPassword = me.sign_in_methods.includes('password')
  const queryClient = useQueryClient()
  const router = useRouter()
  const remove = useMutation({
    ...deleteMeMutation(),
    // The account is gone: drop everything cached about it and leave the signed-in space.
    onSuccess: async () => {
      queryClient.clear()
      await router.navigate({ to: '/' })
    },
  })
  const removeError = remove.isError
    ? remove.error instanceof ApiError && remove.error.code === 'staff_account'
      ? t('staffAccount')
      : t('deleteFailed')
    : undefined

  return (
    <AppShell>
      <main className="px-5 pt-14 pb-22 md:px-[8vw] md:pt-20">
        <Eyebrow>{t('eyebrow')}</Eyebrow>
        <h1 className="mb-3 text-display-l">{t('title')}</h1>
        <p className="text-muted">
          <span className="sr-only">{t('email')} </span>
          {me.email}
        </p>
        <section aria-labelledby="password-title" className="mt-12 max-w-[420px]">
          <h2 id="password-title" className="mb-2 text-[30px] leading-tight">
            {t('passwordTitle')}
          </h2>
          {hasPassword ? (
            <ChangePasswordForm
              onSubmit={({ currentPassword, newPassword }) =>
                change.mutateAsync({ body: { current_password: currentPassword, new_password: newPassword } })
              }
              pending={change.isPending}
              errors={{ currentPassword: errors.currentPassword, newPassword: errors.password, form: errors.form }}
              success={change.isSuccess ? t('changed') : undefined}
            />
          ) : (
            <>
              <p className="mb-4 text-muted">{t('googleOnly')}</p>
              <Link to="/forgot-password" className="underline underline-offset-4">
                {t('setPassword')}
              </Link>
            </>
          )}
        </section>
        <section aria-labelledby="stored-title" className="mt-12 max-w-[560px]">
          <h2 id="stored-title" className="mb-2 text-[30px] leading-tight">
            {t('storedTitle')}
          </h2>
          <ul className="list-disc space-y-1 pl-5">
            {(['account', 'wishes', 'plans', 'quotes', 'sessions'] as const).map((key) => (
              <li key={key}>{t(`stored.${key}`)}</li>
            ))}
          </ul>
          <p className="mt-3 text-muted">{t('storedNever')}</p>
        </section>
        <DeleteAccount
          staff={me.role !== 'client'}
          onConfirm={() => remove.mutate({})}
          pending={remove.isPending}
          error={removeError}
        />
      </main>
    </AppShell>
  )
}
