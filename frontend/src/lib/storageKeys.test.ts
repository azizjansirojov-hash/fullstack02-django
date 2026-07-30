import { afterEach, describe, expect, it } from 'vitest'
import {
  INTRO_SEEN_KEY,
  INTRO_SEEN_KEY_LEGACY,
  READER_SPEED_KEY,
  READER_SPEED_KEY_LEGACY,
  THEME_KEY,
  migrateAllLegacyBrowserStorage,
  migrateLegacyStorageKey,
  readerModeKey,
  readerPageKey,
  storageGet,
} from './storageKeys'

afterEach(() => {
  localStorage.clear()
  sessionStorage.clear()
})

describe('migrateLegacyStorageKey', () => {
  it('copies luma_* legacy value to the new key and removes the old key', () => {
    localStorage.setItem(READER_SPEED_KEY_LEGACY, '2')
    migrateLegacyStorageKey(localStorage, READER_SPEED_KEY_LEGACY, READER_SPEED_KEY)
    expect(localStorage.getItem(READER_SPEED_KEY)).toBe('2')
    expect(localStorage.getItem(READER_SPEED_KEY_LEGACY)).toBeNull()
  })

  it('does not overwrite an existing new-key value', () => {
    localStorage.setItem(READER_SPEED_KEY, '3')
    localStorage.setItem(READER_SPEED_KEY_LEGACY, '1')
    migrateLegacyStorageKey(localStorage, READER_SPEED_KEY_LEGACY, READER_SPEED_KEY)
    expect(localStorage.getItem(READER_SPEED_KEY)).toBe('3')
    expect(localStorage.getItem(READER_SPEED_KEY_LEGACY)).toBeNull()
  })

  it('is a no-op when neither key exists (fresh user)', () => {
    expect(() =>
      migrateLegacyStorageKey(localStorage, READER_SPEED_KEY_LEGACY, READER_SPEED_KEY),
    ).not.toThrow()
    expect(localStorage.getItem(READER_SPEED_KEY)).toBeNull()
    expect(storageGet(localStorage, READER_SPEED_KEY, READER_SPEED_KEY_LEGACY)).toBeNull()
  })
})

describe('migrateAllLegacyBrowserStorage', () => {
  it('migrates fixed keys and slug-scoped reader keys on bootstrap', () => {
    localStorage.setItem(INTRO_SEEN_KEY_LEGACY, '1')
    localStorage.setItem('luma-theme', 'light')
    localStorage.setItem('luma-reader:my-book:page', '4')
    localStorage.setItem('luma-reader:my-book:mode', 'pdf')
    sessionStorage.setItem(INTRO_SEEN_KEY_LEGACY, '1')

    migrateAllLegacyBrowserStorage()

    expect(localStorage.getItem(INTRO_SEEN_KEY)).toBe('1')
    expect(localStorage.getItem(INTRO_SEEN_KEY_LEGACY)).toBeNull()
    expect(localStorage.getItem(THEME_KEY)).toBe('light')
    expect(localStorage.getItem('luma-theme')).toBeNull()
    expect(localStorage.getItem(readerPageKey('my-book'))).toBe('4')
    expect(localStorage.getItem('luma-reader:my-book:page')).toBeNull()
    expect(localStorage.getItem(readerModeKey('my-book'))).toBe('pdf')
    expect(localStorage.getItem('luma-reader:my-book:mode')).toBeNull()
    expect(sessionStorage.getItem(INTRO_SEEN_KEY)).toBe('1')
    expect(sessionStorage.getItem(INTRO_SEEN_KEY_LEGACY)).toBeNull()
  })

  it('leaves a fresh user with empty storage error-free', () => {
    expect(() => migrateAllLegacyBrowserStorage()).not.toThrow()
    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
  })
})
