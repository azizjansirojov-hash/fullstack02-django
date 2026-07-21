const ICONS = {
    back: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/></svg>',
    focus: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M17 8C8 10 5.9 16.17 3.82 21.34L5.71 22l1-2.3A4.94 4.94 0 0 0 8 20C19 20 22 3 22 3c-1 2-8 2.25-13 3.25S2 11.5 2 13.25s1.75 3.75 1.75 3.75S7 8 17 8z"/></svg>',
    page: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zM6 4h5v8l-2.5-1.5L6 12V4z"/></svg>',
    prev: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z"/></svg>',
    next: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/></svg>',
    zoomOut: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14zM7 9h5v1H7z"/></svg>',
    zoomIn: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14zM7 9h5v1H7V9zm2.5 2.5H11V7h1v4.5H16v1h-4.5V17h-1v-4.5H7v-1h2.5z"/></svg>',
    search: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>',
    dark: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3a9 9 0 1 0 9 9c0-.46-.04-.92-.1-1.36a5.389 5.389 0 0 1-4.4 2.26 5.403 5.403 0 0 1-3.14-9.8c-.44-.06-.9-.1-1.36-.1z"/></svg>',
    bookmark: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M17 3H7c-1.1 0-2 .9-2 2v16l7-3 7 3V5c0-1.1-.9-2-2-2z"/></svg>',
    outline: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 13h2v-2H3v2zm0 4h2v-2H3v2zm0-8h2V7H3v2zm4 4h14v-2H7v2zm0 4h14v-2H7v2zM7 7v2h14V7H7z"/></svg>',
    fullscreen: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z"/></svg>',
    print: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 8H5c-1.66 0-3 1.34-3 3v6h4v4h12v-4h4v-6c0-1.66-1.34-3-3-3zm-3 11H8v-5h8v5zm3-7c-.55 0-1-.45-1-1s.45-1 1-1 1 .45 1 1-.45 1-1 1zm-1-9H6v4h12V3z"/></svg>',
    download: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/></svg>',
    lock: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z"/></svg>',
    share: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 16.08c-.76 0-1.44.3-1.96.77L8.91 12.7c.05-.23.09-.46.09-.7s-.04-.47-.09-.7l7.05-4.11c.54.5 1.25.81 2.04.81 1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3c0 .24.04.47.09.7L8.04 9.81C7.5 9.31 6.79 9 6 9c-1.66 0-3 1.34-3 3s1.34 3 3 3c.79 0 1.5-.31 2.04-.81l7.12 4.16c-.05.21-.08.43-.08.65 0 1.61 1.31 2.92 2.92 2.92s2.92-1.31 2.92-2.92-1.31-2.92-2.92-2.92z"/></svg>',
    listen: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 1a9 9 0 0 0-9 9v7c0 1.66 1.34 3 3 3h3v-8H5v-2c0-3.87 3.13-7 7-7s7 3.13 7 7v2h-4v8h3c1.66 0 3-1.34 3-3v-7a9 9 0 0 0-9-9z"/></svg>',
    play: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>',
    pause: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>',
};

/**
 * @param {object} options
 * @param {HTMLElement} options.mount
 * @param {string} options.title
 * @param {string} options.author
 * @param {'flipbook'|'pdf'} options.mode
 * @param {boolean} options.hasPdf
 * @param {boolean} options.hasAudio
 * @param {(action: string) => void} options.onAction
 */
export function mountReaderToolbar(options) {
    const { mount, onAction, mode, title = "", author = "", hasPdf = false, hasAudio = false } = options;
    if (!mount) return null;

    const downloadLocked = !hasPdf;
    const listenDisabled = !hasAudio;
    const pdfTabDisabled = !hasPdf;
    const initialTab = mode === "pdf" && hasPdf ? "page" : "focus";

    mount.innerHTML = `
        <div class="reader-chrome" data-mode="${mode}">
            <header class="reader-chrome__header">
                <button type="button" class="reader-chrome__back" data-action="back" aria-label="Kutubxonaga qaytish">
                    ${ICONS.back}
                    <span>Kutubxonaga qaytish</span>
                </button>
                <div class="reader-chrome__meta">
                    <h1 class="reader-chrome__title">${escapeHtml(title)}</h1>
                    <p class="reader-chrome__author">${escapeHtml(author)}</p>
                </div>
                <div class="reader-chrome__header-spacer" aria-hidden="true"></div>
            </header>

            <div class="reader-chrome__panel" id="reader-chrome-panel">
                <div class="reader-toolbar__row reader-toolbar__row--top">
                    <div class="reader-toolbar__tabs" role="tablist" aria-label="O'qish rejimi">
                        <button type="button" class="reader-toolbar__tab${initialTab === "focus" ? " is-active" : ""}" role="tab" data-action="focus" aria-label="Real Book rejimi" aria-selected="${initialTab === "focus"}">
                            ${ICONS.focus}
                            <span>Fokus</span>
                        </button>
                        <button type="button" class="reader-toolbar__tab${initialTab === "page" ? " is-active" : ""}" role="tab" data-action="page" aria-label="PDF rejimi" aria-selected="${initialTab === "page"}" ${pdfTabDisabled ? 'disabled aria-disabled="true"' : ""}>
                            ${ICONS.page}
                            <span>PDF</span>
                        </button>
                    </div>
                    <div class="reader-toolbar__top-end">
                        <button type="button" class="reader-toolbar__icon-btn reader-toolbar__icon-btn--text" id="btn-font-size" data-action="font-settings" aria-label="Shrift sozlamalari" title="Shrift sozlamalari">
                            <span aria-hidden="true">Aa</span>
                        </button>
                        <button type="button" class="reader-toolbar__icon-btn reader-toolbar__icon-btn--text" id="btn-line-height" data-action="line-height" aria-label="Satr oralig'i" title="Satr oralig'i">
                            <span aria-hidden="true">Tt</span>
                        </button>
                        <button type="button" class="reader-toolbar__listen" data-action="listen" aria-label="Tinglash" ${listenDisabled ? 'disabled aria-disabled="true"' : ""}>
                            ${ICONS.listen}
                            <span>Tinglash</span>
                        </button>
                    </div>
                </div>

                <div class="reader-toolbar__row reader-toolbar__row--bottom">
                    <div class="reader-toolbar__group reader-toolbar__group--pages">
                        <button type="button" class="reader-toolbar__icon-btn" data-action="prev" aria-label="Oldingi sahifa">${ICONS.prev}</button>
                        <span class="reader-toolbar__page-label" id="reader-page-count" aria-live="polite">1 betdan 1-bet</span>
                        <button type="button" class="reader-toolbar__icon-btn" data-action="next" aria-label="Keyingi sahifa">${ICONS.next}</button>
                    </div>

                    <span class="reader-toolbar__divider" aria-hidden="true"></span>

                    <div class="reader-toolbar__group reader-toolbar__group--zoom" data-zoom-group>
                        <button type="button" class="reader-toolbar__icon-btn" data-action="zoom-out" aria-label="Kichiklashtirish">${ICONS.zoomOut}</button>
                        <span class="reader-toolbar__zoom" id="reader-zoom-label">100%</span>
                        <button type="button" class="reader-toolbar__icon-btn" data-action="zoom-in" aria-label="Kattalashtirish">${ICONS.zoomIn}</button>
                    </div>

                    <span class="reader-toolbar__divider" aria-hidden="true"></span>

                    <div class="reader-toolbar__group reader-toolbar__group--tools">
                        <button type="button" class="reader-toolbar__icon-btn" data-action="search" aria-label="Qidirish">${ICONS.search}</button>
                        <button type="button" class="reader-toolbar__icon-btn" data-action="dark" aria-label="Tungi rejim">${ICONS.dark}</button>
                        <button type="button" class="reader-toolbar__icon-btn" data-action="bookmark" aria-label="Xatcho'p" id="reader-bookmark-btn">${ICONS.bookmark}</button>
                        <button type="button" class="reader-toolbar__icon-btn" data-action="outline" aria-label="Mundarija">${ICONS.outline}</button>
                        <button type="button" class="reader-toolbar__icon-btn" data-action="fullscreen" aria-label="To'liq ekran">${ICONS.fullscreen}</button>
                    </div>

                    <span class="reader-toolbar__divider" aria-hidden="true"></span>

                    <div class="reader-toolbar__group reader-toolbar__group--actions">
                        <button type="button" class="reader-toolbar__action" data-action="print" aria-label="Chop etish">
                            ${ICONS.print}
                            <span>Chop etish</span>
                        </button>
                        <button type="button" class="reader-toolbar__action reader-toolbar__action--primary${downloadLocked ? " is-locked" : ""}" data-action="download" aria-label="Yuklab olish" ${downloadLocked ? 'aria-disabled="true"' : ""}>
                            ${downloadLocked ? ICONS.lock : ICONS.download}
                            <span>Yuklab olish</span>
                        </button>
                        <button type="button" class="reader-toolbar__action" data-action="share" aria-label="Ulashish">
                            ${ICONS.share}
                            <span>Ulashish</span>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;

    let viewTab = initialTab;

    mount.addEventListener("click", (event) => {
        const btn = event.target.closest("[data-action]");
        if (!btn || btn.disabled || btn.getAttribute("aria-disabled") === "true") return;

        const action = btn.dataset.action;
        if (action === "focus" || action === "page") {
            setViewTab(action);
        }
        onAction?.(action);
    });

    function setViewTab(tab) {
        viewTab = tab;
        mount.querySelectorAll(".reader-toolbar__tab").forEach((el) => {
            const active = el.dataset.action === tab;
            el.classList.toggle("is-active", active);
            el.setAttribute("aria-selected", String(active));
        });
    }

    return {
        setPage(current, total) {
            const node = mount.querySelector("#reader-page-count");
            if (node) node.textContent = `${total} betdan ${current}-bet`;
            const prevBtn = mount.querySelector("[data-action='prev']");
            const nextBtn = mount.querySelector("[data-action='next']");
            if (prevBtn) prevBtn.disabled = current <= 1;
            if (nextBtn) nextBtn.disabled = current >= total;
        },
        setZoom(zoom) {
            const node = mount.querySelector("#reader-zoom-label");
            if (node) node.textContent = `${Math.round(zoom * 100)}%`;
        },
        setBookmarked(isBookmarked) {
            const btn = mount.querySelector("#reader-bookmark-btn");
            if (btn) btn.classList.toggle("is-active", isBookmarked);
        },
        setDarkActive(isActive) {
            const btn = mount.querySelector("[data-action='dark']");
            if (btn) {
                btn.classList.toggle("is-active", isActive);
                btn.setAttribute("aria-pressed", String(isActive));
            }
        },
        setViewTab,
        getViewTab: () => viewTab,
        setMode(readerMode) {
            const isFlip = readerMode === "flipbook";
            mount.querySelector(".reader-chrome")?.setAttribute("data-mode", readerMode);
            setViewTab(isFlip ? "focus" : "page");
        },
        setNavigationEnabled(enabled) {
            mount.querySelectorAll("[data-action='prev'], [data-action='next']").forEach((btn) => {
                btn.disabled = !enabled;
            });
        },
    };
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text || "";
    return div.innerHTML;
}

export { ICONS };
