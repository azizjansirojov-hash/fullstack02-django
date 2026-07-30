/**
 * Sentence highlight — parity with reader-orchestrator.js highlightSentence().
 * Spans live inside flip pages (.page > .page-content > .reader-sentence).
 */

export type HighlightSentenceOptions = {
  /** 0-based flip page index currently shown (left page of a spread). */
  currentPageIndex?: number | null
}

/**
 * True when the sentence's page is on the visible flip spread.
 * Portrait: exact page. Landscape spread: current page or the next (right) page.
 */
export function shouldScrollToSentence(
  sentencePageIndex: number | null,
  currentPageIndex: number | null | undefined,
): boolean {
  if (sentencePageIndex == null || currentPageIndex == null) return false
  return (
    sentencePageIndex === currentPageIndex ||
    sentencePageIndex === currentPageIndex + 1
  )
}

export function highlightSentence(
  index: number,
  root: ParentNode | Document | null | undefined = document,
  options: HighlightSentenceOptions = {},
): void {
  const scope = root?.querySelectorAll ? root : document
  scope.querySelectorAll('.reader-sentence.is-active').forEach((node) => {
    node.classList.remove('is-active')
  })
  const target = scope.querySelector(`[data-sentence-index="${index}"]`)
  if (!target) return
  target.classList.add('is-active')
  const pageIdx = pageIndexForSentence(index, scope)
  if (shouldScrollToSentence(pageIdx, options.currentPageIndex)) {
    target.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

/**
 * Find 0-based flip page index containing a sentence span (for optional navigation).
 */
export function pageIndexForSentence(
  index: number,
  root: ParentNode | Document | null | undefined = document,
): number | null {
  const scope = root?.querySelectorAll ? root : document
  const target = scope.querySelector(`[data-sentence-index="${index}"]`)
  if (!target) return null
  const pageEl = target.closest('.page')
  if (!pageEl?.parentElement) return null
  const pages = Array.from(pageEl.parentElement.querySelectorAll(':scope > .page'))
  const idx = pages.indexOf(pageEl)
  return idx >= 0 ? idx : null
}
