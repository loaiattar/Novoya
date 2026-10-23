import { describe, expect, it } from 'vitest'

import en from '../../i18n/locales/en/errors.json'
import { accountError, invalidInputFieldErrors, passwordSignInErrorKey, signInErrorKey } from './errors'
import { displayName, safeRedirect } from './session'

describe('displayName', () => {
  it('uses the first name', () => {
    expect(displayName({ first_name: 'Léa', email: 'lea@example.com' })).toBe('Léa')
  })

  it('uses the first word of name when first_name is missing', () => {
    expect(
      displayName({ first_name: null, name: 'Léa Martin', email: 'lea@example.com' }),
    ).toBe('Léa')
  })

  it('falls back to the email when there is no name', () => {
    expect(displayName({ first_name: null, name: null, email: 'lea@example.com' })).toBe(
      'lea@example.com',
    )
    expect(displayName({ first_name: '  ', name: '  ', email: 'lea@example.com' })).toBe(
      'lea@example.com',
    )
  })
})

describe('safeRedirect', () => {
  it('keeps a page of the app', () => {
    expect(safeRedirect('/wishes/new?x=1')).toBe('/wishes/new?x=1')
  })

  it('accepts up to 512 characters, like the API', () => {
    const longest = '/' + 'a'.repeat(511)
    expect(safeRedirect(longest)).toBe(longest)
    expect(safeRedirect(longest + 'a')).toBe('/')
  })

  it.each([undefined, '', 'https://evil.com', '//evil.com', '/\\evil.com', '/a\nb', 42])(
    'falls back to / for %j',
    (target) => {
      expect(safeRedirect(target)).toBe('/')
    },
  )
})

describe('signInErrorKey', () => {
  it('is null without an error', () => {
    expect(signInErrorKey(undefined)).toBeNull()
  })

  it('gives the key of a known code and a fallback for the others', () => {
    expect(signInErrorKey('account_disabled')).toBe('signIn.account_disabled')
    expect(signInErrorKey('oauth_cancelled')).toBe('signIn.oauth_cancelled')
    expect(signInErrorKey('something_new')).toBe('signIn.unknown')
  })

  it('has a text for every key it can give', () => {
    const codes = Object.keys(en.signIn)
    for (const code of [...codes, 'something_new']) {
      const key = signInErrorKey(code)!.replace('signIn.', '')
      expect(en.signIn).toHaveProperty(key)
    }
  })
})

describe('passwordSignInErrorKey', () => {
  it('gives the key of a known code', () => {
    expect(passwordSignInErrorKey('invalid_credentials')).toBe('password.invalid_credentials')
    expect(passwordSignInErrorKey('email_not_verified')).toBe('password.email_not_verified')
  })

  it('reads a rate limit like too many attempts', () => {
    expect(passwordSignInErrorKey('too_many_requests')).toBe('password.too_many_attempts')
  })

  it('has a fallback for anything else', () => {
    expect(passwordSignInErrorKey(undefined)).toBe('password.unknown')
    expect(passwordSignInErrorKey('something_new')).toBe('password.unknown')
  })

  it('has a text for every key it can give', () => {
    for (const code of [...Object.keys(en.password), 'too_many_requests', 'something_new']) {
      const key = passwordSignInErrorKey(code).replace('password.', '')
      expect(en.password).toHaveProperty(key)
    }
  })
})

describe('accountError', () => {
  it('puts an e-mail or password error next to its field', () => {
    expect(accountError('invalid_email')).toEqual({ key: 'account.invalid_email', field: 'email' })
    expect(accountError('email_already_used')).toEqual({ key: 'account.email_already_used', field: 'email' })
    expect(accountError('weak_password')).toEqual({ key: 'account.weak_password', field: 'password' })
  })

  it('reads a wrong password as the current one: only the change of password sends it', () => {
    expect(accountError('invalid_credentials')).toEqual({
      key: 'account.invalid_credentials',
      field: 'currentPassword',
    })
  })

  it('leaves the other errors to the whole form', () => {
    expect(accountError('invalid_token')).toEqual({ key: 'account.invalid_token' })
    expect(accountError('too_many_requests')).toEqual({ key: 'account.too_many_attempts' })
    expect(accountError('something_new')).toEqual({ key: 'account.unknown' })
    expect(accountError(undefined)).toEqual({ key: 'account.unknown' })
  })

  it('has a text for every key it can give', () => {
    for (const code of [...Object.keys(en.account), 'too_many_requests', 'something_new']) {
      expect(en.account).toHaveProperty(accountError(code).key.replace('account.', ''))
    }
  })
})

describe('invalidInputFieldErrors', () => {
  it('puts a missing or blank name next to its field', () => {
    expect(invalidInputFieldErrors('first_name: Field required')).toEqual({
      firstName: 'account.first_name_required',
    })
    expect(invalidInputFieldErrors('last_name: String should have at least 1 character')).toEqual({
      lastName: 'account.last_name_required',
    })
  })

  it('puts a too-long name next to its field', () => {
    expect(invalidInputFieldErrors('first_name: String should have at most 100 characters')).toEqual({
      firstName: 'account.first_name_too_long',
    })
  })

  it('can mark both fields at once', () => {
    expect(
      invalidInputFieldErrors('first_name: Field required; last_name: String should have at most 100 characters'),
    ).toEqual({
      firstName: 'account.first_name_required',
      lastName: 'account.last_name_too_long',
    })
  })

  it('has a text for every key it can give', () => {
    const detail = 'first_name: Field required; last_name: String should have at most 100 characters'
    for (const key of Object.values(invalidInputFieldErrors(detail))) {
      expect(en.account).toHaveProperty(key.replace('account.', ''))
    }
  })
})
