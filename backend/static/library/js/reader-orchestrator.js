import { getReadingMode, setReadingMode, withMode } from "./hooks/use-reading-mode.js";
import { mountPdfReader } from "./pdf-reader-view.js";
import { mountReaderToolbar } from "./reader-toolbar.js";
import { createAudioPlayer } from "./hooks/use-audio-player.js";
import { createAudioSync } from "./hooks/use-audio-sync.js";
import { mountAudioPlaybackBar } from "./audio-playback-bar.js";

const root = document.getElementById("book-reader");
if (!root) {
    // Not on the reader page.
} else {
    const slug = root.dataset.slug;
    const source = document.getElementById("book-source");
    const flipMount = document.getElementById("book-mount");
    const pdfMount = document.getElementById("pdf-reader");
    const counter = document.getElementById("book-counter");
    const loading = document.getElementById("book-loading");
    const hasPdf = Boolean(root.dataset.pdfUrl);
    const hasAudio = Boolean(root.dataset.audioUrl);

    let currentMode = getReadingMode(slug);
    if (currentMode === "pdf" && !hasPdf) {
        currentMode = setReadingMode(slug, "flip");
    }

    let pdfApi = null;
    let currentPage = 1;
    let totalPages = 1;
    let flipZoom = 1;
    let pdfZoom = 1;
    let toolbar = null;
    let audioPlaybar = null;
    let audioShell = null;
    let searchPanel = null;
    let outlinePanel = null;

    const BOOKMARK_KEY = `luma-reader:${slug}:bookmarks`;
    const THEME_KEY = "luma-reader:theme";

    function applyFlipZoom(level) {
        flipZoom = Math.max(0.75, Math.min(2, level));
        root.style.setProperty("--flip-zoom", String(flipZoom));
        toolbar?.setZoom(flipZoom);
    }

    function applyPdfZoom(level) {
        pdfZoom = Math.max(0.75, Math.min(2, level));
        pdfApi?.setZoom(pdfZoom);
        toolbar?.setZoom(pdfZoom);
    }

    function syncZoomLabel() {
        toolbar?.setZoom(currentMode === "pdf" ? pdfZoom : flipZoom);
    }

    function isLightTheme() {
        return root.classList.contains("is-light");
    }

    function applyTheme(isLight) {
        root.classList.toggle("is-light", isLight);
        document.body.classList.toggle("reader-light", isLight);
        toolbar?.setDarkActive(!isLight);
        try {
            localStorage.setItem(THEME_KEY, isLight ? "light" : "dark");
        } catch (_e) {
            // ignore
        }
    }

    function loadSavedTheme() {
        try {
            return localStorage.getItem(THEME_KEY) === "light";
        } catch (_e) {
            return false;
        }
    }

    function dismissLoading() {
        loading?.classList.add("is-hidden");
    }

    function isFlipReady() {
        return Boolean(
            flipMount && (flipMount.querySelector(".page") || flipMount.querySelector(".stf__parent"))
        );
    }

    function syncFlipCounterFromDom() {
        const counterText = counter?.textContent || "";
        const match = counterText.match(/^(\d+)\s*\/\s*(\d+)/);
        if (match) {
            currentPage = parseInt(match[1], 10);
            totalPages = parseInt(match[2], 10);
        }
        toolbar?.setPage(currentPage, totalPages);
        toolbar?.setBookmarked(isPageBookmarked(currentPage));
    }

    function getBookmarks() {
        try {
            return JSON.parse(localStorage.getItem(BOOKMARK_KEY) || "[]");
        } catch (_e) {
            return [];
        }
    }

    function saveBookmarks(list) {
        try {
            localStorage.setItem(BOOKMARK_KEY, JSON.stringify(list));
        } catch (_e) {
            // ignore
        }
    }

    function isPageBookmarked(page) {
        return getBookmarks().includes(page);
    }

    function toggleBookmark(page) {
        const list = getBookmarks();
        const idx = list.indexOf(page);
        if (idx >= 0) {
            list.splice(idx, 1);
        } else {
            list.push(page);
        }
        saveBookmarks(list);
        toolbar?.setBookmarked(list.includes(page));
    }

    function updateCounter() {
        if (currentMode === "pdf" && counter) {
            counter.textContent = `${currentPage} / ${totalPages} sahifa`;
        }
        toolbar?.setPage(currentPage, totalPages);
        toolbar?.setBookmarked(isPageBookmarked(currentPage));
    }

    function showAudioBar() {
        const bar = audioShell?.querySelector(".audio-playback");
        if (bar) bar.removeAttribute("hidden");
    }

    function mountPdfIfNeeded() {
        if (pdfApi || !pdfMount) return;
        toolbar?.setNavigationEnabled(false);
        pdfApi = mountPdfReader(pdfMount, source, {
            onReady: ({ totalPages: pages }) => {
                totalPages = Math.max(1, pages || 1);
                currentPage = 1;
                dismissLoading();
                updateCounter();
                toolbar?.setNavigationEnabled(true);
            },
        });
        totalPages = Math.max(1, pdfApi?.getTotalPages?.() || 1);
        currentPage = 1;
        updateCounter();
    }

    function applyMode(mode, { fromUser = false } = {}) {
        const priorMode = currentMode;
        currentMode = setReadingMode(slug, mode);
        if (currentMode === "pdf" && !hasPdf) {
            currentMode = setReadingMode(slug, "flip");
        }

        const isPdf = currentMode === "pdf";
        const flipReady = isFlipReady();

        root.setAttribute("data-reader-mode", currentMode);
        if (isPdf) {
            root.setAttribute("data-skip-flip", "true");
        } else {
            root.removeAttribute("data-skip-flip");
        }

        if (pdfMount) {
            pdfMount.hidden = !isPdf;
            if (isPdf) pdfMount.removeAttribute("hidden");
        }
        if (flipMount) {
            flipMount.hidden = isPdf;
            if (!isPdf) flipMount.removeAttribute("hidden");
        }

        toolbar?.setMode(isPdf ? "pdf" : "flipbook");
        syncZoomLabel();

        if (isPdf) {
            dismissLoading();
            mountPdfIfNeeded();
            if (pdfApi) pdfApi.setZoom(pdfZoom);
        } else if (!flipReady) {
            if (fromUser && priorMode === "pdf") {
                window.location.assign(withMode(window.location.href, "flip"));
                return;
            }
        } else {
            syncFlipCounterFromDom();
        }
    }

    function ensureSearchPanel() {
        if (searchPanel) return searchPanel;
        searchPanel = document.createElement("div");
        searchPanel.className = "reader-chrome__search";
        searchPanel.hidden = true;
        searchPanel.innerHTML = `
            <label class="visually-hidden" for="reader-search-input">Matn ichida qidirish</label>
            <input type="search" id="reader-search-input" placeholder="Matn ichida qidirish…" autocomplete="off">
        `;
        root.appendChild(searchPanel);
        const input = searchPanel.querySelector("#reader-search-input");
        input.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                searchPanel.hidden = true;
            }
        });
        return searchPanel;
    }

    function ensureOutlinePanel() {
        if (outlinePanel) return outlinePanel;
        const paragraphs = Array.from(source?.querySelectorAll("p") || [])
            .map((p, i) => ({ index: i + 1, text: (p.textContent || "").trim() }))
            .filter((p) => p.text);
        outlinePanel = document.createElement("div");
        outlinePanel.className = "reader-chrome__outline";
        outlinePanel.hidden = true;
        outlinePanel.innerHTML = `
            <p class="reader-chrome__outline-title">Mundarija</p>
            <ul class="reader-chrome__outline-list">
                ${paragraphs.map((p) => `
                    <li><button type="button" data-outline-page="${p.index}">${escapeHtml(p.text.slice(0, 60))}${p.text.length > 60 ? "…" : ""}</button></li>
                `).join("")}
            </ul>
        `;
        outlinePanel.addEventListener("click", (event) => {
            const btn = event.target.closest("[data-outline-page]");
            if (!btn) return;
            const page = parseInt(btn.dataset.outlinePage, 10);
            if (currentMode === "pdf") {
                currentPage = page;
                pdfApi?.setPage(page);
                updateCounter();
            } else {
                window.LumaFlipReaderBridge?.turnToPage?.(page - 1);
            }
            outlinePanel.hidden = true;
        });
        root.appendChild(outlinePanel);
        return outlinePanel;
    }

    toolbar = mountReaderToolbar({
        mount: document.getElementById("reader-toolbar-root"),
        mode: currentMode === "pdf" ? "pdf" : "flipbook",
        title: root.dataset.title || "",
        author: root.dataset.author || "",
        hasPdf,
        hasAudio,
        onAction(action) {
            if (action === "prev") {
                if (currentMode === "pdf") {
                    currentPage = Math.max(1, currentPage - 1);
                    pdfApi?.setPage(currentPage);
                    updateCounter();
                } else {
                    window.LumaFlipReaderBridge?.flipPrev();
                }
            } else if (action === "next") {
                if (currentMode === "pdf") {
                    currentPage = Math.min(totalPages, currentPage + 1);
                    pdfApi?.setPage(currentPage);
                    updateCounter();
                } else {
                    window.LumaFlipReaderBridge?.flipNext();
                }
            } else if (action === "zoom-in") {
                if (currentMode === "pdf") {
                    applyPdfZoom(pdfZoom + 0.1);
                } else {
                    applyFlipZoom(flipZoom + 0.1);
                }
            } else if (action === "zoom-out") {
                if (currentMode === "pdf") {
                    applyPdfZoom(pdfZoom - 0.1);
                } else {
                    applyFlipZoom(flipZoom - 0.1);
                }
            } else if (action === "dark") {
                applyTheme(!isLightTheme());
            } else if (action === "download") {
                if (hasPdf) {
                    window.location.href = root.dataset.pdfUrl;
                }
            } else if (action === "listen") {
                if (hasAudio) showAudioBar();
            } else if (action === "back") {
                window.location.href = root.dataset.detailUrl || root.dataset.catalogUrl || "/library/";
            } else if (action === "share") {
                if (navigator.share) {
                    navigator.share({ title: root.dataset.title || document.title, url: window.location.href }).catch(() => {});
                } else {
                    navigator.clipboard?.writeText(window.location.href).catch(() => {});
                }
            } else if (action === "print") {
                window.print();
            } else if (action === "fullscreen") {
                const isFs = document.fullscreenElement || document.webkitFullscreenElement;
                if (!isFs) {
                    const req = root.requestFullscreen || root.webkitRequestFullscreen;
                    if (req) req.call(root).catch(() => {});
                } else {
                    const exit = document.exitFullscreen || document.webkitExitFullscreen;
                    if (exit) exit.call(document).catch(() => {});
                }
            } else if (action === "font-settings" || action === "line-height") {
                // Handled by reader.js listeners on #btn-font-size / #btn-line-height.
            } else if (action === "bookmark") {
                toggleBookmark(currentPage);
            } else if (action === "search") {
                const panel = ensureSearchPanel();
                panel.hidden = !panel.hidden;
                if (!panel.hidden) {
                    panel.querySelector("#reader-search-input")?.focus();
                    if (outlinePanel) outlinePanel.hidden = true;
                }
            } else if (action === "outline") {
                const panel = ensureOutlinePanel();
                panel.hidden = !panel.hidden;
                if (!panel.hidden && searchPanel) searchPanel.hidden = true;
            } else if (action === "focus") {
                applyMode("flip", { fromUser: true });
            } else if (action === "page") {
                if (hasPdf) {
                    applyMode("pdf", { fromUser: true });
                }
            }
        },
    });

    root.setAttribute("data-reader-mode", currentMode);
    applyTheme(loadSavedTheme());
    applyFlipZoom(1);
    syncZoomLabel();
    if (currentMode === "pdf") {
        applyMode("pdf");
    } else {
        toolbar?.setViewTab("focus");
    }

    let fullscreenRelayoutTimer = null;
    function scheduleFullscreenRelayout() {
        clearTimeout(fullscreenRelayoutTimer);
        fullscreenRelayoutTimer = setTimeout(() => {
            window.LumaFlipReaderBridge?.relayout?.();
        }, 150);
    }
    document.addEventListener("fullscreenchange", scheduleFullscreenRelayout);
    document.addEventListener("webkitfullscreenchange", scheduleFullscreenRelayout);

    window.addEventListener("luma:flipready", () => {
        dismissLoading();
        if (currentMode !== "pdf") {
            syncFlipCounterFromDom();
        }
    });

    window.addEventListener("luma:pagechange", (event) => {
        if (currentMode !== "pdf") {
            const detail = event.detail || {};
            currentPage = detail.current || 1;
            totalPages = detail.total || 1;
            toolbar?.setPage(currentPage, totalPages);
            toolbar?.setBookmarked(isPageBookmarked(currentPage));
        }
    });

    document.addEventListener("click", (event) => {
        if (searchPanel && !searchPanel.hidden && !searchPanel.contains(event.target) && !event.target.closest("[data-action='search']")) {
            searchPanel.hidden = true;
        }
        if (outlinePanel && !outlinePanel.hidden && !outlinePanel.contains(event.target) && !event.target.closest("[data-action='outline']")) {
            outlinePanel.hidden = true;
        }
    });

    audioShell = document.getElementById("audio-playback-root");
    const player = createAudioPlayer(root.dataset.audioUrl || "");

    let parsedSync = [];
    try {
        const syncNode = document.getElementById("audio-sync-data");
        const raw = syncNode ? syncNode.textContent : "[]";
        parsedSync = JSON.parse(raw);
        if (!Array.isArray(parsedSync)) parsedSync = [];
    } catch (_error) {
        parsedSync = [];
    }

    const sync = createAudioSync(source, parsedSync);

    function seekToSentence(index) {
        const row = sync.goToSentence(index);
        if (!row) return;
        const rows = sync.getRows();
        const withRealTiming = rows.some(
            (item) => typeof item.end === "number" && item.end > 0
        );
        if (withRealTiming && typeof row.start === "number") {
            player.seek(row.start);
        } else {
            player.seek(Math.max(0, index) * 4);
        }
    }

    audioPlaybar = mountAudioPlaybackBar(audioShell, {
        hasAudio,
        toggle() {
            if (player.audio.paused) {
                player.play().catch(() => {
                    audioPlaybar?.showError("Audio ijro etilmadi.");
                });
            } else {
                player.pause();
            }
            audioPlaybar?.setToggleIcon(player.audio.paused);
        },
        isPaused: () => player.audio.paused,
        pause: () => player.pause(),
        setSpeed: (speed) => player.setRate(speed),
        toggleMute: () => player.toggleMute(),
        seekRatio: (ratio) => {
            const state = player.getState();
            if (state.duration) {
                player.seek(state.duration * ratio);
            }
        },
        prevSentence() {
            seekToSentence(sync.getActiveIndex() - 1);
        },
        nextSentence() {
            seekToSentence(sync.getActiveIndex() + 1);
        },
    });

    player.onError(() => {
        audioPlaybar?.showError("Audio fayl mavjud emas yoki yuklanmadi.");
    });

    function highlightSentence(index) {
        document.querySelectorAll(".reader-sentence.is-active").forEach((node) => {
            node.classList.remove("is-active");
        });
        const target = document.querySelector(`[data-sentence-index="${index}"]`);
        if (target) {
            target.classList.add("is-active");
            target.scrollIntoView({ behavior: "smooth", block: "center" });
        }
    }

    sync.subscribe((index, total) => {
        highlightSentence(index);
        audioPlaybar?.setSentence(index, total);
    });

    player.audio.addEventListener("timeupdate", () => {
        const state = player.getState();
        const idx = sync.setFromTime(state.currentTime);
        const percent = state.duration ? (state.currentTime / state.duration) * 100 : 0;
        audioPlaybar?.setSeek(percent);
        highlightSentence(idx);
    });

    if (window.location.hash.includes("autoplay=1") && hasAudio) {
        showAudioBar();
        player.play().catch(() => {
            audioPlaybar?.showError("Audio ijro etilmadi.");
        });
    }

    toolbar?.setBookmarked(isPageBookmarked(currentPage));
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text || "";
    return div.innerHTML;
}
