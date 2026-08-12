import { cleanup, fireEvent, render, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import AudioListenMode from '../../components/reader/AudioListenMode'

vi.mock('../../api/library', () => ({
  saveReadingProgress: vi.fn().mockResolvedValue({ response: { ok: true }, data: {} }),
}))

const manifest = {
  slug: 'playback-book',
  title: 'Playback kitob',
  body: 'Birinchi jumla. Ikkinchi jumla.',
  audio_sync: [
    { start: 0, end: 2, index: 0, text: 'Birinchi jumla.' },
    { start: 2, end: 5, index: 1, text: 'Ikkinchi jumla.' },
  ],
  audio_chapters: [
    { id: 1, title: '1-qism', url: '/library/media/playback-book/audio/1/', order: 0 },
  ],
  reading_progress: {
    exists: false,
    mode: 'listen',
    chapter_id: null,
    position: 0,
    page: 0,
    status: 'reading',
  },
  has_audio: true,
}

describe('useAudioPlayback src stability', () => {
  afterEach(() => {
    cleanup()
  })

  beforeEach(() => {
    vi.clearAllMocks()
    HTMLMediaElement.prototype.play = vi.fn().mockResolvedValue(undefined)
    HTMLMediaElement.prototype.pause = vi.fn()
    HTMLMediaElement.prototype.load = vi.fn()
    Element.prototype.scrollIntoView = vi.fn()
  })

  it('does not call load() again when play state updates (regression: aborted playback)', async () => {
    render(<AudioListenMode slug="playback-book" manifest={manifest} />)
    const audio = document.querySelector('audio') as HTMLAudioElement
    expect(audio).toBeTruthy()

    const loadMock = HTMLMediaElement.prototype.load as ReturnType<typeof vi.fn>
    // Initial seed may call load once.
    const callsAfterMount = loadMock.mock.calls.length

    Object.defineProperty(audio, 'paused', { configurable: true, value: true, writable: true })
    Object.defineProperty(audio, 'duration', { configurable: true, value: 60 })
    Object.defineProperty(audio, 'currentTime', { configurable: true, value: 0, writable: true })

    fireEvent.click(document.querySelector('.audio-playback__toggle') as HTMLElement)
    fireEvent.play(audio)

    await waitFor(() => {
      expect(HTMLMediaElement.prototype.play).toHaveBeenCalled()
    })

    // Seek UI / timeupdate also update React state — must not re-seed src.
    Object.defineProperty(audio, 'currentTime', { configurable: true, value: 1.25, writable: true })
    fireEvent.timeUpdate(audio)

    expect(loadMock.mock.calls.length).toBe(callsAfterMount)
    expect(audio.getAttribute('src') || audio.src).toContain('/library/media/playback-book/audio/1/')
  })
})
