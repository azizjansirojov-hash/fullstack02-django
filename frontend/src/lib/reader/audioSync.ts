/** Sentence timing index — parity with backend/static/library/js/hooks/use-audio-sync.js */

import { rowsFromSentences, splitSentencesFromBody, type SentenceRow } from './splitSentences'

/** Sync row from manifest `audio_sync` or synthesized from body text. */
export type AudioSyncRow = SentenceRow & {
  index: number
  text?: string
  start?: number
  end?: number
}

export function buildAudioSyncRows(
  body: string | null | undefined,
  syncRows: AudioSyncRow[] | null | undefined,
): AudioSyncRow[] {
  const rawRows: AudioSyncRow[] =
    Array.isArray(syncRows) && syncRows.length
      ? syncRows
      : rowsFromSentences(splitSentencesFromBody(body))
  return rawRows.map((row, index) => ({
    ...row,
    index: typeof row.index === 'number' ? row.index : index,
  }))
}

export function getIndexForTime(rows: AudioSyncRow[], time: number): number {
  if (!rows.length) return 0
  const withRealTiming = rows.some(
    (row) => typeof row.start === 'number' && typeof row.end === 'number' && row.end > 0,
  )
  if (!withRealTiming) {
    return Math.min(rows.length - 1, Math.floor(time / 4))
  }
  const foundIndex = rows.findIndex(
    (row) =>
      typeof row.start === 'number' &&
      typeof row.end === 'number' &&
      time >= row.start &&
      time <= row.end,
  )
  if (foundIndex >= 0) return foundIndex
  let nearest = 0
  for (let i = 0; i < rows.length; i += 1) {
    const start = rows[i]?.start
    if (typeof start === 'number' && time >= start) {
      nearest = i
    }
  }
  return nearest
}

export function seekTimeForSentence(rows: AudioSyncRow[], index: number): number {
  const row = rows[Math.max(0, Math.min(rows.length - 1, index))]
  if (!row) return 0
  const withRealTiming = rows.some((item) => typeof item.end === 'number' && item.end > 0)
  if (withRealTiming && typeof row.start === 'number') {
    return row.start
  }
  return Math.max(0, index) * 4
}
