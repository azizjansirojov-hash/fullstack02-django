import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { saveReadingProgress } from '../../api/library'
import {
  resolveChapterIndex,
  shouldThrottleProgressSave,
} from './audioProgress'
import {
  buildAudioSyncRows,
  getIndexForTime,
  seekTimeForSentence,
} from './audioSync'
import type { AudioSyncRow } from './audioSync'
import { splitSentencesFromBody } from './splitSentences'
import {
  READER_SPEED_KEY,
  READER_SPEED_KEY_LEGACY,
  storageGet,
  storageSet,
} from '../storageKeys'
import type { AudioChapter, ReaderManifest } from '../../types/library'

export const AUDIO_SPEED_STEPS = [1, 1.25, 1.5, 2]

function loadSpeedIndex() {
  try {
    const raw = storageGet(localStorage, READER_SPEED_KEY, READER_SPEED_KEY_LEGACY)
    if (raw === null) return 0
    const idx = parseInt(raw, 10)
    return Number.isFinite(idx) && idx >= 0 && idx < AUDIO_SPEED_STEPS.length ? idx : 0
  } catch {
    return 0
  }
}

/** Exported for tests — apply stored speed index to an HTMLAudioElement. */
export function applyPlaybackRate(audio: HTMLAudioElement | null, speedIndex = loadSpeedIndex()) {
  if (!audio) return AUDIO_SPEED_STEPS[0] ?? 1
  const rate = AUDIO_SPEED_STEPS[speedIndex] ?? 1
  audio.playbackRate = rate
  return rate
}

/**
 * Shared audio playback + sentence sync (Django orchestrator parity).
 * @param {{ slug, manifest, autoplay?, onActiveSentenceChange? }} options
 */
export function useAudioPlayback({
  slug,
  manifest,
  autoplay = false,
  onActiveSentenceChange,
}: {
  slug: string
  manifest: ReaderManifest
  autoplay?: boolean
  onActiveSentenceChange?: (index: number) => void
}) {
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const normalizedSyncRows = useMemo<AudioSyncRow[]>(
    () =>
      manifest.audio_sync.map((row, index) => ({
        ...row,
        index: row.index ?? index,
        text: row.text ?? '',
        start: row.start ?? 0,
        end: row.end ?? 0,
      })),
    [manifest.audio_sync],
  )
  const syncRows = useMemo(
    () => buildAudioSyncRows(manifest.body, normalizedSyncRows),
    [manifest.body, normalizedSyncRows],
  )
  const sentenceTotal = syncRows.length || splitSentencesFromBody(manifest.body).length
  // Memoize so play/pause/seek state updates do not rebuild this array and
  // re-trigger the src/load effect (which aborts in-progress playback).
  const chapters = useMemo(
    () =>
      manifest.audio_chapters.filter(
        (chapter): chapter is AudioChapter => Boolean(chapter.url),
      ),
    [manifest.audio_chapters],
  )

  const savedProgress = manifest.reading_progress
  const initialChapterIndex = resolveChapterIndex(
    chapters.map((chapter) => ({ ...chapter, id: chapter.id ?? 0 })),
    savedProgress.exists ? savedProgress.chapter_id : null,
  )
  const savedPosition =
    savedProgress?.exists && typeof savedProgress.position === 'number'
      ? savedProgress.position
      : 0

  const [chapterIndex, setChapterIndex] = useState(initialChapterIndex)
  const [activeSentenceIndex, setActiveSentenceIndex] = useState(0)
  const [speedIndex, setSpeedIndex] = useState(() => loadSpeedIndex())
  const [isPaused, setIsPaused] = useState(true)
  const [seekPercent, setSeekPercent] = useState(0)
  const [error, setError] = useState('')
  const [resumePending, setResumePending] = useState(
    savedPosition > 0 || initialChapterIndex > 0,
  )

  const lastSavedAtRef = useRef(0)
  const pendingSaveRef = useRef<{ position: number; chapterIdx: number } | null>(null)
  const autoplayAttemptedRef = useRef(false)
  const chapterIndexRef = useRef(chapterIndex)
  chapterIndexRef.current = chapterIndex

  const persistProgress = useCallback(
    async (position: number, chapterIdx: number, { force = false }: { force?: boolean } = {}) => {
      if (!slug || !chapters.length) return
      const now = Date.now()
      if (!force && shouldThrottleProgressSave(lastSavedAtRef.current, now)) {
        pendingSaveRef.current = { position, chapterIdx }
        return
      }
      lastSavedAtRef.current = now
      pendingSaveRef.current = null
      const chapter = chapters[chapterIdx]
      try {
        // Omit page — API preserves flip/pdf page when mode=listen.
        await saveReadingProgress(slug, {
          mode: 'listen',
          position: Math.max(0, Number(position) || 0),
          chapter_id: chapter?.id ?? null,
        })
      } catch {
        /* offline */
      }
    },
    [slug, chapters],
  )

  const flushPendingSave = useCallback(() => {
    const pending = pendingSaveRef.current
    if (pending) {
      persistProgress(pending.position, pending.chapterIdx, { force: true })
    }
  }, [persistProgress])

  const updateSentenceFromTime = useCallback(
    (time: number) => {
      const idx = getIndexForTime(syncRows, time)
      setActiveSentenceIndex(idx)
      onActiveSentenceChange?.(idx)
      return idx
    },
    [syncRows, onActiveSentenceChange],
  )

  const goToChapter = useCallback(
    (
      index: number,
      { autoplayNext = true, seekTo = null }: { autoplayNext?: boolean; seekTo?: number | null } = {},
    ) => {
      const audio = audioRef.current
      if (!audio || !chapters.length) return
      const next = Math.max(0, Math.min(chapters.length - 1, index))
      const chapter = chapters[next]
      if (!chapter?.url) return
      setChapterIndex(next)
      audio.pause()
      const targetTime = seekTo != null ? seekTo : 0
      setSeekPercent(0)
      updateSentenceFromTime(targetTime)

      const applySeekAndMaybePlay = () => {
        try {
          audio.currentTime = targetTime
        } catch {
          /* ignore seek before ready */
        }
        if (autoplayNext) {
          audio
            .play()
            .then(() => setIsPaused(false))
            .catch(() => setError('Audio ijro etilmadi.'))
        } else {
          setIsPaused(true)
        }
      }

      const absoluteUrl = new URL(chapter.url, window.location.href).href
      if (audio.src === absoluteUrl && audio.readyState >= 1) {
        applySeekAndMaybePlay()
      } else {
        const onReady = () => {
          audio.removeEventListener('loadedmetadata', onReady)
          applySeekAndMaybePlay()
        }
        audio.addEventListener('loadedmetadata', onReady)
        audio.src = chapter.url
        audio.load()
      }
      persistProgress(targetTime, next, { force: true })
    },
    [chapters, persistProgress, updateSentenceFromTime],
  )

  const seekToSentence = useCallback(
    (index: number) => {
      const audio = audioRef.current
      if (!audio) return
      const clamped = Math.max(0, Math.min(sentenceTotal - 1, index))
      const time = seekTimeForSentence(syncRows, clamped)
      audio.currentTime = time
      setActiveSentenceIndex(clamped)
      onActiveSentenceChange?.(clamped)
      const duration = audio.duration || 0
      if (duration) setSeekPercent((time / duration) * 100)
    },
    [sentenceTotal, syncRows, onActiveSentenceChange],
  )

  const initialChapterUrl = chapters[initialChapterIndex]?.url ?? ''
  const hasSeededSrcRef = useRef(false)

  useEffect(() => {
    const audio = audioRef.current
    if (!audio || !initialChapterUrl) return undefined
    // Seed once. Later chapter changes go through goToChapter — never reload
    // here on play/pause/seek state updates (that aborted playback before).
    if (hasSeededSrcRef.current) return undefined
    hasSeededSrcRef.current = true
    audio.src = initialChapterUrl
    audio.preload = 'metadata'
    audio.load()
    return undefined
  }, [initialChapterUrl])

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return undefined
    const audioElement = audio

    function onLoadedMetadata() {
      applyPlaybackRate(audioElement, speedIndex)
      if (resumePending && savedPosition > 0) {
        audioElement.currentTime = savedPosition
        updateSentenceFromTime(savedPosition)
        const duration = audioElement.duration || 0
        if (duration) setSeekPercent((savedPosition / duration) * 100)
        setResumePending(false)
      }
      if (autoplay && !autoplayAttemptedRef.current) {
        autoplayAttemptedRef.current = true
        audioElement
          .play()
          .then(() => setIsPaused(false))
          .catch(() => setError('Audio ijro etilmadi.'))
      }
    }

    function onTimeUpdate() {
      const time = audioElement.currentTime || 0
      updateSentenceFromTime(time)
      const duration = audioElement.duration || 0
      setSeekPercent(duration ? (time / duration) * 100 : 0)
      persistProgress(time, chapterIndexRef.current)
    }

    function onPause() {
      setIsPaused(true)
      persistProgress(audioElement.currentTime || 0, chapterIndexRef.current, { force: true })
    }

    function onPlay() {
      setIsPaused(false)
      setError('')
    }

    function onEnded() {
      const idx = chapterIndexRef.current
      if (idx < chapters.length - 1) {
        goToChapter(idx + 1, { autoplayNext: true, seekTo: 0 })
      } else {
        setIsPaused(true)
        persistProgress(audioElement.duration || 0, idx, { force: true })
      }
    }

    function onError() {
      setError('Audio fayl mavjud emas yoki yuklanmadi.')
      setIsPaused(true)
    }

    audioElement.addEventListener('loadedmetadata', onLoadedMetadata)
    audioElement.addEventListener('timeupdate', onTimeUpdate)
    audioElement.addEventListener('pause', onPause)
    audioElement.addEventListener('play', onPlay)
    audioElement.addEventListener('ended', onEnded)
    audioElement.addEventListener('error', onError)

    return () => {
      audioElement.removeEventListener('loadedmetadata', onLoadedMetadata)
      audioElement.removeEventListener('timeupdate', onTimeUpdate)
      audioElement.removeEventListener('pause', onPause)
      audioElement.removeEventListener('play', onPlay)
      audioElement.removeEventListener('ended', onEnded)
      audioElement.removeEventListener('error', onError)
    }
  }, [
    autoplay,
    chapters.length,
    goToChapter,
    persistProgress,
    resumePending,
    savedPosition,
    speedIndex,
    updateSentenceFromTime,
  ])

  useEffect(() => {
    applyPlaybackRate(audioRef.current, speedIndex)
  }, [speedIndex])

  useEffect(() => {
    function onHide() {
      const audio = audioRef.current
      if (!audio) return
      persistProgress(audio.currentTime || 0, chapterIndexRef.current, { force: true })
      flushPendingSave()
    }
    window.addEventListener('pagehide', onHide)
    return () => window.removeEventListener('pagehide', onHide)
  }, [flushPendingSave, persistProgress])

  const togglePlay = useCallback(() => {
    const audio = audioRef.current
    if (!audio) return
    if (audio.paused) {
      audio.play().catch(() => setError('Audio ijro etilmadi.'))
    } else {
      audio.pause()
    }
  }, [])

  /**
   * Start playback from an explicit user gesture (toolbar Tinglash).
   * Same play() entry as modal `#autoplay=1` / togglePlay — does not pause if
   * already playing.
   */
  const startPlayback = useCallback(() => {
    const audio = audioRef.current
    if (!audio) return
    if (!audio.paused) {
      setIsPaused(false)
      return
    }
    audio
      .play()
      .then(() => {
        setIsPaused(false)
        setError('')
      })
      .catch(() => setError('Audio ijro etilmadi.'))
  }, [])

  const seekRatio = useCallback(
    (ratio: number) => {
      const audio = audioRef.current
      if (!audio || !audio.duration) return
      const time = audio.duration * Math.max(0, Math.min(1, ratio))
      audio.currentTime = time
      updateSentenceFromTime(time)
      setSeekPercent(ratio * 100)
    },
    [updateSentenceFromTime],
  )

  const toggleMute = useCallback(() => {
    const audio = audioRef.current
    if (!audio) return false
    audio.muted = !audio.muted
    return audio.muted
  }, [])

  const cycleSpeed = useCallback(() => {
    const audio = audioRef.current
    if (!audio) return AUDIO_SPEED_STEPS[0] ?? 1
    const next = (speedIndex + 1) % AUDIO_SPEED_STEPS.length
    setSpeedIndex(next)
    audio.playbackRate = AUDIO_SPEED_STEPS[next] ?? 1
    try {
      storageSet(localStorage, READER_SPEED_KEY, String(next), READER_SPEED_KEY_LEGACY)
    } catch {
      /* ignore */
    }
    return AUDIO_SPEED_STEPS[next] ?? 1
  }, [speedIndex])

  const pausePlayback = useCallback(() => {
    audioRef.current?.pause()
    setIsPaused(true)
  }, [])

  return {
    audioRef,
    chapters,
    chapterIndex,
    chapter: chapters[chapterIndex],
    activeSentenceIndex,
    sentenceTotal,
    seekPercent,
    isPaused,
    error,
    speedLabel: `${AUDIO_SPEED_STEPS[speedIndex] ?? 1}x`,
    togglePlay,
    startPlayback,
    seekRatio,
    toggleMute,
    cycleSpeed,
    seekToSentence,
    goToChapter,
    pausePlayback,
    hasAudio: chapters.length > 0,
  }
}

