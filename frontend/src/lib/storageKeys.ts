/**
 * Libro.UZ browser storage keys + one-time migration from legacy prefixes.
 *
 * Canonical keys use the `librouz_` prefix. Older browsers may still hold
 * `luma-*` / `libro-*` values; those are copied once at bootstrap (and as a
 * defensive fallback on read), then deleted.
 */

export const INTRO_SEEN_KEY = 'librouz_intro_seen'
export const THEME_KEY = 'librouz_theme'
export const SIDEBAR_COLLAPSE_KEY = 'librouz_sidebar_collapsed'
export const READER_SPEED_KEY = 'librouz_reader_speed'
export const READER_SETTINGS_KEY = 'librouz_reader_settings'
export const LOCALE_KEY = 'librouz_locale'

/** @deprecated Prefer INTRO_SEEN_KEY — kept for tests that assert migration sources */
export const INTRO_SEEN_KEY_LEGACY = 'luma-intro-seen'
/** @deprecated Prefer THEME_KEY */
export const THEME_KEY_LEGACY = 'libro-theme'
/** @deprecated Prefer SIDEBAR_COLLAPSE_KEY */
export const SIDEBAR_COLLAPSE_KEY_LEGACY = 'libro-sidebar-collapsed'
/** @deprecated Prefer READER_SPEED_KEY */
export const READER_SPEED_KEY_LEGACY = 'luma-reader:speed'
/** @deprecated Prefer READER_SETTINGS_KEY */
export const READER_SETTINGS_KEY_LEGACY = 'luma-reader:settings'
/** @deprecated Prefer LOCALE_KEY */
export const LOCALE_KEY_LEGACY = 'libro-locale'

export function readerPageKey(slug: string): string {
  return `librouz_reader_${slug}_page`
}

export function readerPageKeyLegacy(slug: string): string {
  return `luma-reader:${slug}:page`
}

export function readerModeKey(slug: string): string {
  return `librouz_reader_${slug}_mode`
}

export function readerModeKeyLegacy(slug: string): string {
  return `luma-reader:${slug}:mode`
}

/**
 * Copy `oldKey` → `newKey` once when the new key is empty, then delete `oldKey`.
 * Safe no-op when storage is unavailable or neither key has data.
 */
export function migrateLegacyStorageKey(
  storage: Storage,
  oldKey: string,
  newKey: string,
): void {
  if (!oldKey || !newKey || oldKey === newKey) return
  try {
    const current = storage.getItem(newKey)
    if (current !== null) {
      storage.removeItem(oldKey)
      return
    }
    const legacy = storage.getItem(oldKey)
    if (legacy === null) return
    storage.setItem(newKey, legacy)
    storage.removeItem(oldKey)
  } catch {
    /* private mode / blocked storage */
  }
}

const FIXED_LOCAL_MIGRATIONS: ReadonlyArray<readonly [string, string]> = [
  ['luma-intro-seen', INTRO_SEEN_KEY],
  ['libro-intro-seen', INTRO_SEEN_KEY],
  ['luma-theme', THEME_KEY],
  ['libro-theme', THEME_KEY],
  ['luma-sidebar-collapsed', SIDEBAR_COLLAPSE_KEY],
  ['libro-sidebar-collapsed', SIDEBAR_COLLAPSE_KEY],
  ['luma-reader:speed', READER_SPEED_KEY],
  ['libro-reader:speed', READER_SPEED_KEY],
  ['luma-reader:settings', READER_SETTINGS_KEY],
  ['libro-reader:settings', READER_SETTINGS_KEY],
  ['luma-locale', LOCALE_KEY],
  ['libro-locale', LOCALE_KEY],
]

const FIXED_SESSION_MIGRATIONS: ReadonlyArray<readonly [string, string]> = [
  ['luma-intro-seen', INTRO_SEEN_KEY],
  ['libro-intro-seen', INTRO_SEEN_KEY],
]

/**
 * Migrate slug-scoped reader keys:
 *   luma-reader:<slug>:page  → librouz_reader_<slug>_page
 *   luma-reader:<slug>:mode  → librouz_reader_<slug>_mode
 * (also accepts libro-reader:… variants)
 */
function migratePatternReaderKeys(storage: Storage): void {
  let keys: string[]
  try {
    keys = []
    for (let i = 0; i < storage.length; i += 1) {
      const k = storage.key(i)
      if (k) keys.push(k)
    }
  } catch {
    return
  }

  const pageRe = /^(?:luma|libro)-reader:([^:]+):page$/
  const modeRe = /^(?:luma|libro)-reader:([^:]+):mode$/

  for (const oldKey of keys) {
    const pageMatch = pageRe.exec(oldKey)
    if (pageMatch?.[1]) {
      migrateLegacyStorageKey(storage, oldKey, readerPageKey(pageMatch[1]))
      continue
    }
    const modeMatch = modeRe.exec(oldKey)
    if (modeMatch?.[1]) {
      migrateLegacyStorageKey(storage, oldKey, readerModeKey(modeMatch[1]))
    }
  }
}

/** Run once at app bootstrap (main.tsx) before any feature reads storage. */
export function migrateAllLegacyBrowserStorage(): void {
  try {
    for (const [oldKey, newKey] of FIXED_LOCAL_MIGRATIONS) {
      migrateLegacyStorageKey(localStorage, oldKey, newKey)
    }
    migratePatternReaderKeys(localStorage)
  } catch {
    /* ignore */
  }
  try {
    for (const [oldKey, newKey] of FIXED_SESSION_MIGRATIONS) {
      migrateLegacyStorageKey(sessionStorage, oldKey, newKey)
    }
  } catch {
    /* ignore */
  }
}

/** Read new key; fall back to legacy and migrate when legacy is hit. */
export function storageGet(
  storage: Storage,
  key: string,
  legacyKey?: string,
): string | null {
  try {
    const current = storage.getItem(key)
    if (current !== null) return current
    if (!legacyKey) return null
    migrateLegacyStorageKey(storage, legacyKey, key)
    return storage.getItem(key)
  } catch {
    return null
  }
}

export function storageSet(
  storage: Storage,
  key: string,
  value: string,
  legacyKey?: string,
): void {
  try {
    storage.setItem(key, value)
    if (legacyKey) storage.removeItem(legacyKey)
  } catch {
    /* private mode / blocked storage */
  }
}

export function storageRemove(
  storage: Storage,
  key: string,
  legacyKey?: string,
): void {
  try {
    storage.removeItem(key)
    if (legacyKey) storage.removeItem(legacyKey)
  } catch {
    /* ignore */
  }
}
