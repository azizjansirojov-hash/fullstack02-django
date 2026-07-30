import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import AudioListenMode from './AudioListenMode'
import * as libraryApi from '../../api/library'

vi.mock('../../api/library', () => ({
  saveReadingProgress: vi.fn().mockResolvedValue({ response: { ok: true }, data: {} }),
}))

const manifest = {
  slug: 'listen-book',
  title: 'Listen kitob',
  body: 'Birinchi jumla. Ikkinchi jumla.',
  audio_sync: [
    { start: 0, end: 2, index: 0, text: 'Birinchi jumla.' },
    { start: 2, end: 5, index: 1, text: 'Ikkinchi jumla.' },
  ],
  audio_chapters: [
    { id: 1, title: '1-qism', url: '/library/media/listen-book/audio/1/', order: 0 },
    { id: 2, title: '2-qism', url: '/library/media/listen-book/audio/2/', order: 1 },
  ],
  reading_progress: {
    exists: true,
    mode: 'listen',
    chapter_id: 2,
    position: 12.5,
    page: 0,
    status: 'reading',
  },
}

describe('AudioListenMode', () => {
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

  function getAudio() {
    return document.querySelector('audio.reader-listen__audio')
  }

  it('renders playback bar and sentence text', async () => {
    render(<AudioListenMode slug="listen-book" manifest={manifest} />)

    expect(screen.getByText('Tinglash')).toBeInTheDocument()
    expect(screen.getByText('Birinchi jumla.')).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /1-qism/i })).toBeInTheDocument()
  })

  it('switches chapter and saves progress on chapter select', async () => {
    render(<AudioListenMode slug="listen-book" manifest={manifest} />)
    const audio = getAudio()
    Object.defineProperty(audio, 'duration', { configurable: true, value: 120 })

    fireEvent.click(screen.getByRole('option', { name: /1-qism/i }))

    await waitFor(() => {
      expect(libraryApi.saveReadingProgress).toHaveBeenCalled()
    })

    const lastCall = libraryApi.saveReadingProgress.mock.calls.at(-1)
    expect(lastCall[0]).toBe('listen-book')
    expect(lastCall[1]).toMatchObject({
      mode: 'listen',
      chapter_id: 1,
    })
  })

  it('saves progress on pause', async () => {
    render(<AudioListenMode slug="listen-book" manifest={manifest} />)
    const audio = getAudio()
    Object.defineProperty(audio, 'currentTime', { configurable: true, value: 9.5, writable: true })
    Object.defineProperty(audio, 'duration', { configurable: true, value: 120 })
    Object.defineProperty(audio, 'paused', { configurable: true, value: false, writable: true })

    fireEvent.click(screen.getByLabelText('Ijro etish'))
    fireEvent.pause(getAudio())

    await waitFor(() => {
      expect(libraryApi.saveReadingProgress).toHaveBeenCalledWith(
        'listen-book',
        expect.objectContaining({ mode: 'listen', chapter_id: 2 }),
      )
    })
  })

  it('resumes from saved chapter and position on metadata load', async () => {
    render(<AudioListenMode slug="listen-book" manifest={manifest} />)
    const audio = getAudio()
    Object.defineProperty(audio, 'currentTime', { configurable: true, value: 0, writable: true })
    Object.defineProperty(audio, 'duration', { configurable: true, value: 120 })

    fireEvent.loadedMetadata(audio)

    await waitFor(() => {
      expect(audio.currentTime).toBe(12.5)
    })
    expect(screen.getByText(/2-qism · 2\/2/)).toBeInTheDocument()
  })

  it('highlights active sentence from sync timing on timeupdate', async () => {
    render(<AudioListenMode slug="listen-book" manifest={manifest} />)
    const audio = getAudio()
    Object.defineProperty(audio, 'currentTime', { configurable: true, value: 3, writable: true })
    Object.defineProperty(audio, 'duration', { configurable: true, value: 120 })

    fireEvent.timeUpdate(audio)

    const active = document.querySelector('[data-sentence-index="1"].is-active')
    expect(active).toBeTruthy()
  })

  it('shows empty state when no audio chapters', () => {
    render(
      <AudioListenMode
        slug="listen-book"
        manifest={{ ...manifest, audio_chapters: [] }}
      />,
    )
    expect(screen.getByText('Audio mavjud emas.')).toBeInTheDocument()
  })
})

