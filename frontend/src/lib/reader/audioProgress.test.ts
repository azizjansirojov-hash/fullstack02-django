import { afterEach, describe, expect, it } from 'vitest'
import {
  PROGRESS_SAVE_INTERVAL_MS,
  resolveChapterIndex,
  shouldThrottleProgressSave,
} from './audioProgress'
import { AUDIO_SPEED_STEPS, applyPlaybackRate } from './useAudioPlayback'
import {
  READER_SPEED_KEY,
  READER_SPEED_KEY_LEGACY,
  storageGet,
  storageRemove,
  storageSet,
} from '../storageKeys'

describe('audioProgress', () => {
  it('throttles saves within interval', () => {
    const now = 10_000
    expect(shouldThrottleProgressSave(now - 1000, now)).toBe(true)
    expect(shouldThrottleProgressSave(now - PROGRESS_SAVE_INTERVAL_MS, now)).toBe(false)
  })

  it('resolves chapter index from saved chapter_id', () => {
    const chapters = [
      { id: 10, title: 'A' },
      { id: 20, title: 'B' },
    ]
    expect(resolveChapterIndex(chapters, 20)).toBe(1)
    expect(resolveChapterIndex(chapters, null)).toBe(0)
    expect(resolveChapterIndex(chapters, 999)).toBe(0)
  })
})

describe('AUDIO_SPEED_STEPS — localStorage persistence helpers', () => {
  afterEach(() => {
    storageRemove(localStorage, READER_SPEED_KEY, READER_SPEED_KEY_LEGACY)
  })

  it('AUDIO_SPEED_STEPS has 4 entries starting at 1', () => {
    expect(AUDIO_SPEED_STEPS).toHaveLength(4)
    expect(AUDIO_SPEED_STEPS[0]).toBe(1)
  })

  it('stored index round-trips through localStorage', () => {
    const idx = 2 // 1.5x
    storageSet(localStorage, READER_SPEED_KEY, String(idx), READER_SPEED_KEY_LEGACY)
    const restored = parseInt(
      storageGet(localStorage, READER_SPEED_KEY, READER_SPEED_KEY_LEGACY) ?? '0',
      10,
    )
    expect(restored).toBe(idx)
    expect(AUDIO_SPEED_STEPS[restored]).toBe(1.5)
  })

  it('migrates legacy speed key to librouz key', () => {
    localStorage.setItem(READER_SPEED_KEY_LEGACY, '1')
    const restored = storageGet(localStorage, READER_SPEED_KEY, READER_SPEED_KEY_LEGACY)
    expect(restored).toBe('1')
    expect(localStorage.getItem(READER_SPEED_KEY)).toBe('1')
    expect(localStorage.getItem(READER_SPEED_KEY_LEGACY)).toBeNull()
  })

  it('out-of-range stored value falls back to 0', () => {
    storageSet(localStorage, READER_SPEED_KEY, '99', READER_SPEED_KEY_LEGACY)
    const raw = parseInt(
      storageGet(localStorage, READER_SPEED_KEY, READER_SPEED_KEY_LEGACY) ?? '0',
      10,
    )
    const safe = Number.isFinite(raw) && raw >= 0 && raw < AUDIO_SPEED_STEPS.length ? raw : 0
    expect(safe).toBe(0)
  })

  it('applyPlaybackRate sets audio.playbackRate from speed index', () => {
    const audio = { playbackRate: 1 }
    expect(applyPlaybackRate(audio, 2)).toBe(1.5)
    expect(audio.playbackRate).toBe(1.5)
  })

  it('applyPlaybackRate uses stored localStorage index when omitted', () => {
    storageSet(localStorage, READER_SPEED_KEY, '3', READER_SPEED_KEY_LEGACY)
    const audio = { playbackRate: 1 }
    expect(applyPlaybackRate(audio)).toBe(2)
    expect(audio.playbackRate).toBe(2)
  })
})
