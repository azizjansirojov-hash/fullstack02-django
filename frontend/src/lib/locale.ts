/**
 * Locale preference for future i18n. App ships Uzbek-only; LANGUAGE_CODE=uz stays.
 */

import {
  LOCALE_KEY,
  LOCALE_KEY_LEGACY,
  storageGet,
  storageSet,
} from './storageKeys'

export { LOCALE_KEY, LOCALE_KEY_LEGACY }

export type AppLocale = 'uz'

export const SUPPORTED_LOCALES: ReadonlyArray<{
  code: AppLocale
  label: string
}> = [{ code: 'uz', label: 'O‘zbekcha' }]

export function readLocale(): AppLocale {
  const raw = storageGet(localStorage, LOCALE_KEY, LOCALE_KEY_LEGACY)
  if (raw === 'uz') return 'uz'
  return 'uz'
}

export function writeLocale(locale: AppLocale): void {
  storageSet(localStorage, LOCALE_KEY, locale, LOCALE_KEY_LEGACY)
  try {
    document.documentElement.lang = locale
  } catch {
    /* ignore */
  }
}

export function localeLabel(code: AppLocale = readLocale()): string {
  return SUPPORTED_LOCALES.find((l) => l.code === code)?.label || 'O‘zbekcha'
}
