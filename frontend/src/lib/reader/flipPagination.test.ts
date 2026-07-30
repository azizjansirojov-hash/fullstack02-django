import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import {
  buildPageElements,
  escapeHtml,
  getPageDimensions,
  getParagraphsFromBody,
  getSavedPageIndex,
  paginateContent,
} from './flipPagination'

describe('flipPagination parity with Django reader.js', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1200 })
    Object.defineProperty(window, 'innerHeight', { configurable: true, value: 900 })
  })

  afterEach(() => {
    document.body.replaceChildren()
  })

  it('getPageDimensions returns landscape spread sizes', () => {
    const dims = getPageDimensions()
    expect(dims.isPortrait).toBe(false)
    expect(dims.width).toBeGreaterThan(200)
    expect(dims.height).toBeGreaterThan(200)
  })

  it('getPageDimensions returns portrait layout under 720px', () => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 600 })
    const dims = getPageDimensions()
    expect(dims.isPortrait).toBe(true)
  })

  it('paginateContent splits long paragraphs across pages', () => {
    const originalScrollHeight = Object.getOwnPropertyDescriptor(
      HTMLElement.prototype,
      'scrollHeight',
    )
    const originalClientHeight = Object.getOwnPropertyDescriptor(
      HTMLElement.prototype,
      'clientHeight',
    )

    Object.defineProperty(HTMLElement.prototype, 'scrollHeight', {
      configurable: true,
      get() {
        if (this.classList?.contains('page-content')) {
          return (this.innerHTML || '').length > 180 ? 900 : 120
        }
        return originalScrollHeight?.get?.call(this) ?? 0
      },
    })
    Object.defineProperty(HTMLElement.prototype, 'clientHeight', {
      configurable: true,
      get() {
        if (this.classList?.contains('page-content')) return 380
        return originalClientHeight?.get?.call(this) ?? 0
      },
    })

    try {
      const longPara = `${'Word '.repeat(400)}End.`
      const pages = paginateContent([longPara], 280, 380)
      expect(pages.length).toBeGreaterThan(1)
      pages.forEach((html) => {
        expect(html).toMatch(/<p>/)
      })
    } finally {
      if (originalScrollHeight) {
        Object.defineProperty(HTMLElement.prototype, 'scrollHeight', originalScrollHeight)
      }
      if (originalClientHeight) {
        Object.defineProperty(HTMLElement.prototype, 'clientHeight', originalClientHeight)
      }
    }
  })

  it('paginateContent escapes HTML in body text', () => {
    const pages = paginateContent(['<script>alert(1)</script>'], 280, 380)
    expect(pages[0]).not.toContain('<script>')
    expect(pages[0]).toContain(escapeHtml('<script>alert(1)</script>'))
  })

  it('buildPageElements wraps sentences when sentenceWrap is true', () => {
    const elements = buildPageElements(['<p>First. Second.</p>'], { sentenceWrap: true })
    expect(elements).toHaveLength(1)
    const spans = elements[0]!.querySelectorAll('.reader-sentence')
    expect(spans.length).toBe(2)
    expect(spans[0]!.getAttribute('data-sentence-index')).toBe('0')
    expect(spans[1]!.getAttribute('data-sentence-index')).toBe('1')
  })

  it('getParagraphsFromBody splits on blank lines', () => {
    expect(getParagraphsFromBody('A\n\nB')).toEqual(['A', 'B'])
  })

  it('getSavedPageIndex clamps server page to range', () => {
    expect(getSavedPageIndex(10, { exists: true, page: 99 })).toBe(9)
    expect(getSavedPageIndex(10, { exists: false })).toBe(0)
  })

  it('does not collapse a multi-paragraph book body to a single page', () => {
    // Regression for measure-box CSS scoping: body-appended .book-reader__measure
    // must paginate long content. Mock overflow by HTML length like Django's
    // layout would for ~14kb of text on a 400×500 page.
    const originalScrollHeight = Object.getOwnPropertyDescriptor(
      HTMLElement.prototype,
      'scrollHeight',
    )
    const originalClientHeight = Object.getOwnPropertyDescriptor(
      HTMLElement.prototype,
      'clientHeight',
    )

    Object.defineProperty(HTMLElement.prototype, 'scrollHeight', {
      configurable: true,
      get() {
        if (this.classList?.contains('page-content')) {
          const len = (this.innerHTML || '').length
          // ~900 chars ≈ one page at reader font/padding
          return Math.ceil(len / 900) * 500
        }
        return originalScrollHeight?.get?.call(this) ?? 0
      },
    })
    Object.defineProperty(HTMLElement.prototype, 'clientHeight', {
      configurable: true,
      get() {
        if (this.classList?.contains('page-content')) return 500
        return originalClientHeight?.get?.call(this) ?? 0
      },
    })

    try {
      const paragraphs = Array.from({ length: 24 }, (_, i) =>
        `Paragraph ${i + 1}. ${'Lorem ipsum dolor sit amet. '.repeat(12)}`,
      )
      const pages = paginateContent(paragraphs, 400, 500)
      expect(pages.length).toBeGreaterThan(1)
      expect(pages.length).toBeGreaterThanOrEqual(3)
    } finally {
      if (originalScrollHeight) {
        Object.defineProperty(HTMLElement.prototype, 'scrollHeight', originalScrollHeight)
      }
      if (originalClientHeight) {
        Object.defineProperty(HTMLElement.prototype, 'clientHeight', originalClientHeight)
      }
    }
  })
})
