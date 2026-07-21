import { mountReadingModeSelector } from "./reading-mode-selector.js";
import { getReadingMode, withMode } from "./hooks/use-reading-mode.js";

const actions = document.getElementById("reader-actions");
if (!actions) {
    // Not on detail page
} else {
    const slug = actions.dataset.slug;
    const readUrl = actions.dataset.readUrl;
    const audioUrl = actions.dataset.audioUrl;
    const pdfUrl = actions.dataset.pdfUrl;
    const continueBtn = document.getElementById("btn-continue-reading");
    const startOverBtn = document.getElementById("btn-start-over-detail");
    const listenBtn = document.getElementById("btn-listen-detail");
    const downloadBtn = document.getElementById("btn-download-pdf-detail");

    function syncReadLinks(mode) {
        const nextUrl = withMode(readUrl, mode);
        if (continueBtn) continueBtn.href = nextUrl;
        startOverBtn?.setAttribute("data-target-url", nextUrl);
    }

    const selector = mountReadingModeSelector({
        mountId: "reading-mode-selector-detail",
        slug,
        onChange: syncReadLinks,
    });
    syncReadLinks(selector ? selector.getMode() : getReadingMode(slug));

    startOverBtn?.addEventListener("click", () => {
        try {
            localStorage.removeItem(`luma-reader:${slug}:page`);
        } catch (_error) {
            // ignore
        }
        window.location.href = startOverBtn.getAttribute("data-target-url") || readUrl;
    });

    if (!audioUrl) {
        listenBtn.setAttribute("disabled", "true");
        listenBtn.setAttribute("aria-disabled", "true");
    } else {
        listenBtn.addEventListener("click", () => {
            window.location.href = `${withMode(readUrl, getReadingMode(slug))}#autoplay=1`;
        });
    }

    if (!pdfUrl) {
        downloadBtn.classList.add("is-disabled");
        downloadBtn.setAttribute("aria-disabled", "true");
        downloadBtn.addEventListener("click", (event) => event.preventDefault());
    }

    const progressBar = document.getElementById("reader-progress-bar");
    const progressValue = document.getElementById("reader-progress-value");
    let savedPage = 0;
    try {
        const raw = localStorage.getItem(`luma-reader:${slug}:page`);
        savedPage = raw !== null ? Math.max(0, parseInt(raw, 10) || 0) : 0;
    } catch (_error) {
        savedPage = 0;
    }
    const totalEstimate = 120;
    // Show 0% if the user has never opened the book (savedPage === 0)
    const percentage = savedPage === 0
        ? 0
        : Math.max(1, Math.min(100, Math.round((savedPage / totalEstimate) * 100)));
    if (progressBar) progressBar.style.width = `${percentage}%`;
    if (progressValue) progressValue.textContent = `${percentage}%`;
}

