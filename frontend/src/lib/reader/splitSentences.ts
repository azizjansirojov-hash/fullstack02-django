/** Sentence splitting — parity with backend/static/library/js/hooks/split-sentences.js */

export type SentenceRow = {
  index: number
  text: string
  start: number
  end: number
}

export function splitSentences(text: string | null | undefined): string[] {
  const trimmed = (text || '').trim()
  if (!trimmed) return []
  const chunks = trimmed.match(/[^.!?]+[.!?]?/g)
  if (!chunks) return []
  return chunks.map((chunk) => chunk.trim()).filter(Boolean)
}

export function splitSentencesFromBody(body: string | null | undefined): string[] {
  if (!body) return []
  const paragraphs = String(body)
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean)
  if (paragraphs.length) {
    const sentences: string[] = []
    paragraphs.forEach((paragraph) => {
      sentences.push(...splitSentences(paragraph))
    })
    return sentences
  }
  return splitSentences(body)
}

export function rowsFromSentences(sentences: string[]): SentenceRow[] {
  return sentences.map((text, index) => ({ index, text, start: 0, end: 0 }))
}
