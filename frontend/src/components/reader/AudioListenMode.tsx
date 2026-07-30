import { useCallback, useEffect, useMemo } from 'react'
import { splitSentences, splitSentencesFromBody } from '../../lib/reader/splitSentences'
import { buildAudioSyncRows, type AudioSyncRow } from '../../lib/reader/audioSync'
import { highlightSentence } from '../../lib/reader/sentenceHighlight'
import { useAudioPlayback } from '../../lib/reader/useAudioPlayback'
import AudioPlaybackBar from './AudioPlaybackBar'
import type { ReaderManifest } from '../../types/library'

const SPEED_STEPS = [1, 1.25, 1.5, 2]

function bodyParagraphs(body: string) {
  return String(body || '')
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean)
}

function buildParagraphSentenceSpans(
  body: string,
  syncRows: Array<{ index: number; text?: string }>,
) {
  const rows = syncRows.length
    ? syncRows
    : splitSentencesFromBody(body).map((text, index) => ({ index, text, start: 0, end: 0 }))
  const paragraphs = bodyParagraphs(body)
  if (!paragraphs.length) {
    return [
      {
        key: 'p-0',
        spans: rows.map((row) => ({
          index: row.index,
          text: row.text || '',
        })),
      },
    ]
  }
  let cursor = 0
  return paragraphs.map((paragraph, pIndex) => {
    const paraSentenceCount = splitSentences(paragraph).length
    const spans = []
    for (let i = 0; i < paraSentenceCount && cursor < rows.length; i += 1) {
      const row = rows[cursor]
    if (!row) continue
      spans.push({ index: row.index, text: row.text || '' })
      cursor += 1
    }
    return { key: `p-${pIndex}`, spans }
  })
}

/**
 * Standalone scrollable listen view (legacy/tests). Production reader uses FlipReaderView overlay.
 */
export default function AudioListenMode({
  slug,
  manifest,
  autoplay = false,
}: {
  slug: string
  manifest: ReaderManifest
  autoplay?: boolean
}) {
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
  const paragraphSpans = useMemo(
    () => buildParagraphSentenceSpans(manifest.body, syncRows),
    [manifest.body, syncRows],
  )

  const handleSentenceChange = useCallback((index: number) => {
    highlightSentence(index, document)
  }, [])

  const audio = useAudioPlayback({
    slug,
    manifest,
    autoplay,
    onActiveSentenceChange: handleSentenceChange,
  })

  useEffect(() => {
    highlightSentence(audio.activeSentenceIndex, document)
  }, [audio.activeSentenceIndex])

  if (!audio.hasAudio) {
    return (
      <p className="reader-listen__empty" role="status">
        Audio mavjud emas.
      </p>
    )
  }

  return (
    <div className="reader-listen">
      <audio ref={audio.audioRef} className="reader-listen__audio" preload="metadata" />

      <article className="reader-listen__text" aria-label="Kitob matni">
        {paragraphSpans.map((paragraph) => (
          <p key={paragraph.key}>
            {paragraph.spans.map((span) => (
              <span
                key={`s-${span.index}`}
                className={`reader-sentence${audio.activeSentenceIndex === span.index ? ' is-active' : ''}`}
                data-sentence-index={span.index}
              >
                {span.text}{' '}
              </span>
            ))}
          </p>
        ))}
      </article>

      <AudioPlaybackBar
        chapters={audio.chapters}
        chapterIndex={audio.chapterIndex}
        chapterTitle={audio.chapter?.title}
        sentenceIndex={audio.activeSentenceIndex}
        sentenceTotal={audio.sentenceTotal}
        seekPercent={audio.seekPercent}
        isPaused={audio.isPaused}
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
        onToggleMute={audio.toggleMute}
        speedLabel={audio.speedLabel}
      />
    </div>
  )
}

export { SPEED_STEPS }

