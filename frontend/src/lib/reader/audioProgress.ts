/**
 * Audio progress persistence cadence.
 *
 * Django reader (reader-orchestrator.js): does NOT PUT audio position/chapter_id —
 * flip/PDF saves always send position: 0. There is no timeupdate throttle to match.
 *
 * React listen mode saves on pause, chapter change, page hide, and at most every
 * PROGRESS_SAVE_INTERVAL_MS while playing (never on every timeupdate).
 */
export const PROGRESS_SAVE_INTERVAL_MS = 5000

export type AudioChapterRef = {
  id: number | string
  title?: string
}

export function shouldThrottleProgressSave(lastSavedAtMs: number, nowMs = Date.now()): boolean {
  return nowMs - lastSavedAtMs < PROGRESS_SAVE_INTERVAL_MS
}

export function resolveChapterIndex(
  chapters: AudioChapterRef[] | null | undefined,
  chapterId: number | string | null | undefined,
): number {
  if (!chapters?.length) return 0
  if (chapterId == null || chapterId === '') return 0
  const idx = chapters.findIndex((ch) => ch.id === chapterId)
  return idx >= 0 ? idx : 0
}
