import { describe, expect, it } from 'vitest'
import { buildAudioSyncRows, getIndexForTime, seekTimeForSentence } from './audioSync'

describe('audioSync parity with Django use-audio-sync.js', () => {
  const realRows = [
    { start: 0, end: 2.5, index: 0, text: 'First.' },
    { start: 2.5, end: 5.0, index: 1, text: 'Second.' },
    { start: 5.0, end: 8.0, index: 2, text: 'Third.' },
  ]

  it('uses 4-second fallback when no real timings', () => {
    const rows = buildAudioSyncRows('One. Two. Three.', [])
    expect(getIndexForTime(rows, 0)).toBe(0)
    expect(getIndexForTime(rows, 3.9)).toBe(0)
    expect(getIndexForTime(rows, 4)).toBe(1)
    expect(getIndexForTime(rows, 11)).toBe(2)
  })

  it('matches inclusive start/end intervals for real timings', () => {
    expect(getIndexForTime(realRows, 0)).toBe(0)
    expect(getIndexForTime(realRows, 2.5)).toBe(0)
    expect(getIndexForTime(realRows, 2.51)).toBe(1)
    expect(getIndexForTime(realRows, 4.9)).toBe(1)
    expect(getIndexForTime(realRows, 7)).toBe(2)
  })

  it('uses nearest prior start when between sentences', () => {
    expect(getIndexForTime(realRows, 2.51)).toBe(1)
    expect(getIndexForTime(realRows, 5.5)).toBe(2)
  })

  it('seeks to row.start or index*4 like Django seekToSentence', () => {
    expect(seekTimeForSentence(realRows, 1)).toBe(2.5)
    const fallback = buildAudioSyncRows('A. B.', [])
    expect(seekTimeForSentence(fallback, 2)).toBe(8)
  })
})
