import type { ChangeEvent } from 'react'
import type { AudioChapter } from '../../types/library'

type AudioPlaybackBarProps = {
  chapters: AudioChapter[]
  chapterIndex: number
  chapterTitle?: string
  sentenceIndex: number
  sentenceTotal: number
  seekPercent: number
  isPaused: boolean
  isMuted?: boolean
  error: string | null
  onTogglePlay: () => void
  onSeekRatio: (value: number) => void
  onPrevSentence: () => void
  onNextSentence: () => void
  onPrevChapter: () => void
  onNextChapter: () => void
  onSelectChapter: (index: number) => void
  onCycleSpeed: () => void
  onToggleMute: () => void
  onClose?: () => void
  speedLabel: string
}

function IconPlay() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M8 5v14l11-7z" />
    </svg>
  )
}

function IconPause() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" />
    </svg>
  )
}

export default function AudioPlaybackBar({
  chapters,
  chapterIndex,
  chapterTitle,
  sentenceIndex,
  sentenceTotal,
  seekPercent,
  isPaused,
  isMuted = false,
  error,
  onTogglePlay,
  onSeekRatio,
  onPrevSentence,
  onNextSentence,
  onPrevChapter,
  onNextChapter,
  onSelectChapter,
  onCycleSpeed,
  onToggleMute,
  onClose = undefined,
  speedLabel,
}: AudioPlaybackBarProps) {
  const multi = chapters.length > 1
  const chapterLabel =
    multi && chapterTitle
      ? `${chapterTitle} · ${chapterIndex + 1}/${chapters.length}`
      : chapterTitle || `${chapterIndex + 1}-qism`

  return (
    <div className="audio-playback">
      <div className="audio-playback__inner">
        <button
          type="button"
          className="audio-playback__toggle"
          onClick={onTogglePlay}
          aria-label={isPaused ? 'Ijro etish' : 'Pauza'}
        >
          {isPaused ? <IconPlay /> : <IconPause />}
        </button>

        <div className="audio-playback__meta">
          <span className="audio-playback__label">Tinglash</span>
          <span className="audio-playback__chapter">{chapterLabel}</span>
          <span className="audio-playback__count">
            {sentenceIndex + 1} / {sentenceTotal}
          </span>
        </div>

        <input
          type="range"
          className="audio-playback__seek"
          min="0"
          max="100"
          value={Math.round(seekPercent)}
          onChange={(event: ChangeEvent<HTMLInputElement>) => onSeekRatio(Number(event.target.value))}
          aria-label="Ijro holati"
        />

        <div className="audio-playback__controls">
          {multi ? (
            <>
              <button type="button" className="audio-playback__btn" onClick={onPrevChapter}>
                ◀ Qism
              </button>
              <button type="button" className="audio-playback__btn" onClick={onNextChapter}>
                Qism ▶
              </button>
            </>
          ) : null}
          <button type="button" className="audio-playback__btn" onClick={onPrevSentence}>
            Oldingi
          </button>
          <button type="button" className="audio-playback__btn" onClick={onCycleSpeed}>
            {speedLabel}
          </button>
          <button
            type="button"
            className={`audio-playback__btn${isMuted ? ' is-active' : ''}`}
            onClick={onToggleMute}
            aria-label={isMuted ? 'Ovozni yoqish' : 'Ovozsiz'}
            aria-pressed={isMuted}
          >
            {isMuted ? 'Ovozli' : 'Ovozsiz'}
          </button>
          <button type="button" className="audio-playback__btn" onClick={onNextSentence}>
            Keyingi
          </button>
          {onClose ? (
            <button
              type="button"
              className="audio-playback__btn audio-playback__btn--close"
              onClick={onClose}
              aria-label="Yopish"
            >
              Yopish
            </button>
          ) : null}
        </div>

        {multi ? (
          <ul className="audio-playback__playlist" role="listbox" aria-label="Audio qismlar">
            {chapters.map((ch, index) => (
              <li key={ch.id ?? index}>
                <button
                  type="button"
                  className={`audio-playback__track${index === chapterIndex ? ' is-active' : ''}`}
                  role="option"
                  aria-selected={index === chapterIndex}
                  onClick={() => onSelectChapter(index)}
                >
                  <span className="audio-playback__track-index">{index + 1}</span>
                  <span className="audio-playback__track-title">
                    {ch.title || `${index + 1}-qism`}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        ) : null}

        {error ? (
          <p className="audio-playback__error" role="alert">
            {error}
          </p>
        ) : null}
      </div>
    </div>
  )
}

