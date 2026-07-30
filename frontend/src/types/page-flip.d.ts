declare module 'page-flip' {
  export class PageFlip {
    constructor(element: HTMLElement, options: Record<string, unknown>)
    loadFromHTML(pages: HTMLElement[]): void
    getCurrentPageIndex(): number
    getPageCount(): number
    flipPrev(): void
    flipNext(): void
    turnToPage(index: number): void
    destroy(): void
    on(event: 'flip', callback: (event: { data: number }) => void): void
    on(event: 'changeState', callback: (event: { data: string }) => void): void
  }
}
