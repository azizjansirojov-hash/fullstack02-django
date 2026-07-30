import { useCallback, useEffect, useRef, useState } from 'react'
import FlipBookMode from './FlipBookMode'
import AudioPlaybackBar from './AudioPlaybackBar'
import { highlightSentence } from '../../lib/reader/sentenceHighlight'
import { useAudioPlayback } from '../../lib/reader/useAudioPlayback'
import type { ReaderManifest } from '../../types/library'

/**
 * Flip reader with optional audio overlay — Django flip+listen coexistence.
 */
export default function FlipReaderView({
  slug,
  manifest,
  autoplay = false,
}: {
  slug: string
  manifest: ReaderManifest
  autoplay?: boolean
}) {
  const flipRootRef = useRef<HTMLDivElement | null>(null)
  const flipPageIndexRef = useRef(0)
  const [audioBarVisible, setAudioBarVisible] = useState(false)
  const [muted, setMuted] = useState(false)
  const activeSentenceRef = useRef(0)

  const handleSentenceChange = useCallback((index: number) => {
    activeSentenceRef.current = index
    if (flipRootRef.current) {
      highlightSentence(index, flipRootRef.current, {
        currentPageIndex: flipPageIndexRef.current,
      })
    }
  }, [])

  const audio = useAudioPlayback({
    slug,
    manifest,
    autoplay: autoplay && Boolean(manifest.has_audio),
    onActiveSentenceChange: handleSentenceChange,
  })

  const { hasAudio, startPlayback, pausePlayback } = audio

  /** Toolbar Tinglash: reveal bar + start play (user gesture ≈ modal autoplay). */
  const handleListenClick = useCallback(() => {
    if (!hasAudio) return
    setAudioBarVisible(true)
    startPlayback()
  }, [hasAudio, startPlayback])

  useEffect(() => {
    if (autoplay && hasAudio) {
      setAudioBarVisible(true)
    }
  }, [autoplay, hasAudio])

  const handleFlipReady = useCallback(() => {
    highlightSentence(activeSentenceRef.current, flipRootRef.current, {
      currentPageIndex: flipPageIndexRef.current,
    })
  }, [])

  const handlePageChange = useCallback((pageIndex: number) => {
    flipPageIndexRef.current = pageIndex
    highlightSentence(activeSentenceRef.current, flipRootRef.current, {
      currentPageIndex: pageIndex,
    })
  }, [])

  function hideAudioBar() {
    pausePlayback()
    setAudioBarVisible(false)
  }

  function handleToggleMute() {
    const next = audio.toggleMute()
    setMuted(Boolean(next))
  }

  return (
    <div
      ref={flipRootRef}
      className={`flip-reader-view${audioBarVisible ? ' flip-reader-view--audio-open' : ''}`}
    >
      <FlipBookMode
        slug={slug}
        manifest={manifest}
        onFlipReady={handleFlipReady}
        onListenClick={handleListenClick}
        onPageChange={handlePageChange}
      />

      {audio.hasAudio ? (
        <>
          <audio ref={audio.audioRef} className="flip-reader-view__audio" preload="metadata" />
          <div className="flip-reader-view__audio-shell" hidden={!audioBarVisible}>
            <AudioPlaybackBar
              chapters={audio.chapters}
              chapterIndex={audio.chapterIndex}
              chapterTitle={audio.chapter?.title}
              sentenceIndex={audio.activeSentenceIndex}
              sentenceTotal={audio.sentenceTotal}
              seekPercent={audio.seekPercent}
              isPaused={audio.isPaused}
              isMuted={muted}
              error={audio.error}
              onTogglePlay={audio.togglePlay}
              onSeekRatio={(value: number) => audio.seekRatio(value / 100)}
              onPrevSentence={() => audio.seekToSentence(audio.activeSentenceIndex - 1)}
              onNextSentence={() => audio.seekToSentence(audio.activeSentenceIndex + 1)}
              onPrevChapter={() => {
                if (audio.chapterIndex <= 0) {
                  const el = audio.audioRef.current
                  if (el instanceof HTMLAudioElement) el.currentTime = 0
                  return
                }
                audio.goToChapter(audio.chapterIndex - 1, { autoplayNext: true })
              }}
              onNextChapter={() => {
                if (audio.chapterIndex >= audio.chapters.length - 1) return
                audio.goToChapter(audio.chapterIndex + 1, { autoplayNext: true })
              }}
              onSelectChapter={(index: number) => audio.goToChapter(index, { autoplayNext: true })}
              onCycleSpeed={audio.cycleSpeed}
              onToggleMute={handleToggleMute}
              onClose={hideAudioBar}
              speedLabel={audio.speedLabel}
            />
          </div>
        </>
      ) : null}
    </div>
  )
}

