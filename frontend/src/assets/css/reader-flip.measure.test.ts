import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const cssPath = join(
  dirname(fileURLToPath(import.meta.url)),
  '../../assets/css/reader-flip.css',
)

describe('reader-flip.css measure-box scoping', () => {
  const css = readFileSync(cssPath, 'utf8')

  it('defines reader tokens on :root so body-appended measure nodes inherit', () => {
    expect(css).toMatch(/:root\s*\{[^}]*--reader-font-size/s)
    expect(css).toMatch(/:root\s*\{[^}]*--reader-page-padding/s)
    expect(css).toMatch(/:root\s*\{[^}]*--reader-page:/s)
  })

  it('does not nest .book-reader__measure under .flip-book-mode only', () => {
    // The live bug: measure box is appended to document.body, so
    // `.flip-book-mode .book-reader__measure` never matches.
    expect(css).not.toMatch(/\.flip-book-mode\s+\.book-reader__measure/)
    expect(css).toMatch(/\.book-reader__measure\s+\.page-content/)
  })

  it('keeps mount-scoped rules for in-tree nodes (nav, counter, stage)', () => {
    expect(css).toMatch(/\.flip-book-mode\s+\.book-reader__nav-zone/)
    expect(css).toMatch(/\.flip-book-mode\s+\.book-reader__counter/)
    expect(css).toMatch(/\.flip-book-mode\s+\.book-reader__stage/)
  })
})

