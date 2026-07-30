import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  highlightSentence,
  pageIndexForSentence,
  shouldScrollToSentence,
} from './sentenceHighlight'

describe('sentenceHighlight', () => {
  beforeEach(() => {
    Element.prototype.scrollIntoView = vi.fn()
    document.body.innerHTML = `
      <div id="flip-root">
        <div class="page"><div class="page-content">
          <p><span class="reader-sentence" data-sentence-index="0">First.</span></p>
        </div></div>
        <div class="page"><div class="page-content">
          <p><span class="reader-sentence" data-sentence-index="1">Second.</span></p>
        </div></div>
      </div>
    `
  })

  it('toggles is-active on the target span within root scope', () => {
    const root = document.getElementById('flip-root')
    expect(root).not.toBeNull()
    highlightSentence(1, root, { currentPageIndex: 1 })
    expect(root!.querySelector('[data-sentence-index="1"]')!.classList.contains('is-active')).toBe(
      true,
    )
    expect(root!.querySelector('[data-sentence-index="0"]')!.classList.contains('is-active')).toBe(
      false,
    )
  })

  it('scrolls only when sentence is on the current spread', () => {
    const root = document.getElementById('flip-root')
    const scroll = Element.prototype.scrollIntoView as ReturnType<typeof vi.fn>
    highlightSentence(1, root, { currentPageIndex: 0 })
    expect(scroll).toHaveBeenCalled()
    scroll.mockClear()
    highlightSentence(1, root, { currentPageIndex: 3 })
    expect(scroll).not.toHaveBeenCalled()
  })

  it('does not scroll when current page is unknown', () => {
    const root = document.getElementById('flip-root')
    const scroll = Element.prototype.scrollIntoView as ReturnType<typeof vi.fn>
    highlightSentence(0, root)
    expect(scroll).not.toHaveBeenCalled()
  })

  it('finds page index for sentence span', () => {
    const root = document.getElementById('flip-root')
    expect(root).not.toBeNull()
    expect(pageIndexForSentence(0, root)).toBe(0)
    expect(pageIndexForSentence(1, root)).toBe(1)
  })

  it('shouldScrollToSentence covers current and next page of a spread', () => {
    expect(shouldScrollToSentence(0, 0)).toBe(true)
    expect(shouldScrollToSentence(1, 0)).toBe(true)
    expect(shouldScrollToSentence(2, 0)).toBe(false)
    expect(shouldScrollToSentence(null, 0)).toBe(false)
  })
})
