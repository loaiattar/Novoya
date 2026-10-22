import type { Locale } from '../i18n/locale'
import raw from '../../../brand/agency.json'

type Status = 'confirmed' | 'to_check'

type Sourced<T> = {
  value: T
  status: Status
  translation_status?: Partial<Record<Locale, Status>>
  display?: string
}

type Address = {
  street: string
  postal_code: string
  city: string
  country: string
}

type Organisation = {
  name: string
  address?: string
  phone?: string
  contract_number?: string
}

type Localized = Record<Locale, string>

export const LEGAL_KEYS = [
  'publisher',
  'company',
  'legalForm',
  'shareCapital',
  'siren',
  'siret',
  'rcs',
  'vat',
  'atoutFrance',
  'guarantor',
  'insurer',
  'publicationDirector',
  'host',
  'email',
  'address',
  'phone',
] as const

export type LegalKey = (typeof LEGAL_KEYS)[number]

export type LegalLine = { key: LegalKey; value: string }

export type AgencyView = {
  tradeName: string
  displayName: string
  foundedYear?: number
  website?: string
  tagline?: string
  descriptionShort?: string
  email?: string
  phone?: { href: string; display: string }
  address?: string
  social: { network: string; href: string }[]
  logo: { src: string; alt: string; width: number; height: number }
  legalLines: LegalLine[]
}

/** A value the site may show: confirmed, and not a draft translation. */
export function shown<T>(entry: Sourced<T> | undefined): T | undefined {
  if (!entry || entry.status !== 'confirmed') return undefined
  return entry.value
}

function shownText(entry: Sourced<Localized> | undefined, locale: Locale): string | undefined {
  const value = shown(entry)
  if (!value) return undefined
  if (entry?.translation_status?.[locale] === 'to_check') return undefined
  return value[locale] || value.fr
}

function formatAddress(address: Address): string {
  return `${address.street}, ${address.postal_code} ${address.city}`
}

function formatOrganisation(org: Organisation): string {
  return [org.name, org.address, org.contract_number].filter(Boolean).join(' · ')
}

function photoSrc(path: string): string {
  return `/${path.replace(/\.[a-z]+$/i, '')}`
}

type AgencyFile = {
  identity: {
    trade_name: Sourced<string>
    display_name?: Sourced<string>
    company_name?: Sourced<string>
    founded_year?: Sourced<number>
    website?: Sourced<string>
    tagline?: Sourced<Localized>
    description_short?: Sourced<Localized>
  }
  contact: {
    address?: Sourced<Address>
    phone?: Sourced<string> & { display?: string }
    email?: Sourced<string>
  }
  legal: {
    legal_form?: Sourced<string>
    share_capital?: Sourced<{ amount: number; currency: string }>
    siren?: Sourced<string>
    siret?: Sourced<string>
    rcs?: Sourced<string>
    vat_number?: Sourced<string>
    atout_france_registration?: Sourced<string>
    financial_guarantor?: Sourced<Organisation>
    professional_liability_insurer?: Sourced<Organisation>
    publication_director?: Sourced<string>
    host?: Sourced<Organisation>
  }
  social?: Record<string, Sourced<string>>
  images: {
    logo: { value: string; alt?: Localized; status: Status; width: number; height: number }
  }
}

const data = raw as AgencyFile

/** Confirmed agency facts for one language. `to_check` values are omitted. */
export function agencyView(locale: Locale): AgencyView {
  const tradeName = shown(data.identity.trade_name) ?? ''
  const displayName = shown(data.identity.display_name) ?? tradeName
  const email = shown(data.contact.email)
  const address = shown(data.contact.address)
  const phoneValue = shown(data.contact.phone)
  const logoAlt = data.images.logo.alt
  const legalLines: LegalLine[] = []

  const push = (key: LegalKey, value: string | undefined) => {
    if (value) legalLines.push({ key, value })
  }
  push('publisher', displayName)
  push('company', shown(data.identity.company_name))
  push('legalForm', shown(data.legal.legal_form))
  const capital = shown(data.legal.share_capital)
  push('shareCapital', capital ? `${capital.amount} ${capital.currency}` : undefined)
  push('siren', shown(data.legal.siren))
  push('siret', shown(data.legal.siret))
  push('rcs', shown(data.legal.rcs))
  push('vat', shown(data.legal.vat_number))
  push('atoutFrance', shown(data.legal.atout_france_registration))
  const guarantor = shown(data.legal.financial_guarantor)
  push('guarantor', guarantor ? formatOrganisation(guarantor) : undefined)
  const insurer = shown(data.legal.professional_liability_insurer)
  push('insurer', insurer ? formatOrganisation(insurer) : undefined)
  push('publicationDirector', shown(data.legal.publication_director))
  const host = shown(data.legal.host)
  push('host', host ? formatOrganisation(host) : undefined)
  push('email', email)
  push('address', address ? formatAddress(address) : undefined)
  push('phone', data.contact.phone?.status === 'confirmed' ? data.contact.phone.display : undefined)

  return {
    tradeName,
    displayName,
    foundedYear: shown(data.identity.founded_year),
    website: shown(data.identity.website),
    tagline: shownText(data.identity.tagline, locale),
    descriptionShort: shownText(data.identity.description_short, locale),
    email,
    phone:
      phoneValue && data.contact.phone?.display
        ? { href: `tel:${phoneValue}`, display: data.contact.phone.display }
        : undefined,
    address: address ? formatAddress(address) : undefined,
    social: Object.entries(data.social ?? {}).flatMap(([network, entry]) => {
      const href = shown(entry)
      return href ? [{ network, href }] : []
    }),
    logo: {
      src: photoSrc(data.images.logo.value),
      alt: (logoAlt && (logoAlt[locale] || logoAlt.fr)) || tradeName,
      width: data.images.logo.width,
      height: data.images.logo.height,
    },
    legalLines,
  }
}
