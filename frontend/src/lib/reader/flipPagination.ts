/**
 * Flip-book pagination — verbatim port of backend/static/library/js/reader.js
 * (getPageDimensions, paginateContent, buildPageElements, helpers).
 */
import { splitSentences } from './splitSentences'

import {
  READER_SETTINGS_KEY,
  READER_SETTINGS_KEY_LEGACY,
  storageGet,
  storageSet,
} from '../storageKeys'

export const FONT_STEPS = ['0.95rem', '1.05rem', '1.18rem'] as const
export const LINE_STEPS = [1.65, 1.75, 1.9] as const
/** @deprecated Prefer READER_SETTINGS_KEY from storageKeys — kept for test imports */
export const SETTINGS_KEY = READER_SETTINGS_KEY

export type ReaderSettings = {
  fontIndex: number
  lineIndex: number
}

export type PageDimensions = {
  width: number
  height: number
  isPortrait: boolean
}

/** Minimal progress shape used for resume page index (full API type comes in Phase 3). */
export type ReadingProgressPageHint = {
  exists?: boolean
  page?: number
} | null | undefined

export function clampIndex(value: unknown, length: number, fallback: number): number {
  const idx = typeof value === 'number' ? value : fallback
  return Math.max(0, Math.min(length - 1, idx))
}

export function loadReaderSettings(): ReaderSettings {
  try {
    const raw = storageGet(localStorage, READER_SETTINGS_KEY, READER_SETTINGS_KEY_LEGACY) || '{}'
    const stored = JSON.parse(raw) as {
      fontIndex?: unknown
      lineIndex?: unknown
    }
    return {
      fontIndex: clampIndex(stored.fontIndex, FONT_STEPS.length, 1),
      lineIndex: clampIndex(stored.lineIndex, LINE_STEPS.length, 1),
    }
  } catch {
    return { fontIndex: 1, lineIndex: 1 }
  }
}

export function saveReaderSettings(settings: ReaderSettings): void {
  storageSet(
    localStorage,
    READER_SETTINGS_KEY,
    JSON.stringify(settings),
    READER_SETTINGS_KEY_LEGACY,
  )
}

export function cycleFontIndex(fontIndex: number): number {
  return (fontIndex + 1) % FONT_STEPS.length
}

export function cycleLineIndex(lineIndex: number): number {
  return (lineIndex + 1) % LINE_STEPS.length
}

export function applyReaderSettingsToRoot(settings: ReaderSettings = loadReaderSettings()): void {
  // Indices are clampIndex'd into range; non-null assert preserves prior runtime.
  document.documentElement.style.setProperty('--reader-font-size', FONT_STEPS[settings.fontIndex]!)
  document.documentElement.style.setProperty(
    '--reader-line-height',
    String(LINE_STEPS[settings.lineIndex]!),
  )
}

export function prefersReducedMotion(): boolean {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

export function getFlipTime(): number {
  return prefersReducedMotion() ? 0 : 680
}

export function getPageDimensions(): PageDimensions {
  const maxSpreadWidth = Math.min(window.innerWidth * 0.92, 1000)
  const maxHeight = window.innerHeight - 190
  const isPortrait = window.innerWidth < 720

  if (isPortrait) {
    const singleWidth = Math.min(maxSpreadWidth, 420)
    const singleHeight = Math.min(maxHeight, Math.round(singleWidth * 1.38))
    return { width: singleWidth, height: singleHeight, isPortrait: true }
  }

  const pageWidth = Math.floor(maxSpreadWidth / 2)
  const pageHeight = Math.min(maxHeight, Math.round(pageWidth * 1.38))
  return { width: pageWidth, height: pageHeight, isPortrait: false }
}

/** Plain-text body → paragraph strings (Django getParagraphs without DOM source node). */
export function getParagraphsFromBody(body: string | null | undefined): string[] {
  const text = String(body || '').trim()
  if (!text) return []
  return text
    .split(/\n\s*\n/)
    .map((chunk) => chunk.trim())
    .filter(Boolean)
}

export function escapeHtml(text: string): string {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

function createMeasureBox(width: number, height: number): HTMLDivElement {
  const box = document.createElement('div')
  box.className = 'book-reader__measure'
  box.style.cssText =
    `position:fixed;left:-9999px;top:0;width:${width}px;height:${height}px;` +
    'visibility:hidden;pointer-events:none;overflow:hidden;'
  box.innerHTML = '<div class="page-content"></div>'
  document.body.appendChild(box)
  return box
}

function pageFits(measureContent: HTMLElement, html: string): boolean {
  measureContent.innerHTML = html
  return measureContent.scrollHeight <= measureContent.clientHeight + 1
}

function splitParagraphByWords(html: string, measureContent: HTMLElement): string[] {
  const temp = document.createElement('div')
  temp.innerHTML = html
  const text = temp.textContent || ''
  const words = text.split(/\s+/).filter(Boolean)
  if (!words.length) return [html]

  const chunks: string[] = []
  let current: string[] = []

  words.forEach((word) => {
    current.push(word)
    const trial = `<p>${escapeHtml(current.join(' '))}</p>`
    if (!pageFits(measureContent, trial) && current.length > 1) {
      current.pop()
      chunks.push(`<p>${escapeHtml(current.join(' '))}</p>`)
      current = [word]
    }
  })

  if (current.length) {
    chunks.push(`<p>${escapeHtml(current.join(' '))}</p>`)
  }
  return chunks
}

export function paginateContent(paragraphs: string[], width: number, height: number): string[] {
  const measureBox = createMeasureBox(width, height)
  // Structure is always created by createMeasureBox; assert matches prior JS.
  const measureContent = measureBox.querySelector('.page-content') as HTMLElement
  const pages: string[] = []
  let currentHtml = ''

  function flushPage() {
    if (currentHtml.trim()) {
      pages.push(currentHtml)
      currentHtml = ''
    }
  }

  paragraphs.forEach((para) => {
    const paraHtml = `<p>${escapeHtml(para)}</p>`

    if (!currentHtml) {
      if (pageFits(measureContent, paraHtml)) {
        currentHtml = paraHtml
      } else {
        splitParagraphByWords(para, measureContent).forEach((chunk) => {
          if (pageFits(measureContent, currentHtml + chunk)) {
            currentHtml += chunk
          } else {
            flushPage()
            currentHtml = chunk
          }
        })
      }
      return
    }

    const trial = currentHtml + paraHtml
    if (pageFits(measureContent, trial)) {
      currentHtml = trial
    } else {
      flushPage()
      if (pageFits(measureContent, paraHtml)) {
        currentHtml = paraHtml
      } else {
        splitParagraphByWords(para, measureContent).forEach((chunk) => {
          if (pageFits(measureContent, currentHtml + chunk)) {
            currentHtml += chunk
          } else {
            flushPage()
            currentHtml = chunk
          }
        })
      }
    }
  })

  flushPage()
  document.body.removeChild(measureBox)

  if (!pages.length) {
    pages.push('<p></p>')
  }
  return pages
}

function wrapSentences(pageElement: HTMLElement, startIndex: number): number {
  const paragraphs = pageElement.querySelectorAll('.page-content p')
  let sentenceIndex = startIndex
  paragraphs.forEach((paragraph) => {
    const chunks = splitSentences(paragraph.textContent || '')
    if (!chunks.length) return
    paragraph.innerHTML = chunks
      .map((chunk) => {
        const text = escapeHtml(chunk)
        if (!text) return ''
        const html = `<span class="reader-sentence" data-sentence-index="${sentenceIndex}">${text}</span>`
        sentenceIndex += 1
        return html
      })
      .join(' ')
  })
  return sentenceIndex
}

export function buildPageElements(
  pagesHtml: string[],
  { sentenceWrap = false }: { sentenceWrap?: boolean } = {},
): HTMLDivElement[] {
  let globalSentenceIndex = 0
  return pagesHtml.map((html) => {
    const page = document.createElement('div')
    page.className = 'page'
    page.innerHTML = `<div class="page-content">${html}</div>`
    if (sentenceWrap) {
      globalSentenceIndex = wrapSentences(page, globalSentenceIndex)
    }
    return page
  })
}

export function getSavedPageIndex(
  totalPages: number,
  readingProgress: ReadingProgressPageHint,
): number {
  if (readingProgress?.exists && typeof readingProgress.page === 'number') {
    return Math.max(0, Math.min(totalPages - 1, readingProgress.page))
  }
  return 0
}

export const PAGE_FLIP_OPTIONS = {
  size: 'stretch',
  minWidth: 280,
  maxWidth: 520,
  minHeight: 380,
  maxHeight: 900,
  maxShadowOpacity: 0.55,
  showCover: false,
  mobileScrollSupport: false,
  drawShadow: true,
  useMouseEvents: true,
} as const
