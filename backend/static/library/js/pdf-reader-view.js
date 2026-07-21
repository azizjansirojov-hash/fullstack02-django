import { buildSentenceSpans } from "./hooks/split-sentences.js";

function configurePdfWorker() {
    if (typeof window.pdfjsLib === "undefined") return;
    if (window.pdfjsLib.GlobalWorkerOptions?.workerSrc) return;
    const workerSrc = document.getElementById("book-reader")?.dataset.pdfWorkerSrc;
    if (workerSrc) {
        window.pdfjsLib.GlobalWorkerOptions.workerSrc = workerSrc;
    }
}

export function mountPdfReader(container, sourceNode, { onReady } = {}) {
    if (!container || !sourceNode) return null;
    const host = document.getElementById("book-reader");
    const pdfUrl = host?.dataset.pdfUrl || "";
    const paragraphs = Array.from(sourceNode.querySelectorAll("p")).map((p) => p.textContent.trim()).filter(Boolean);
    const sentenceCounter = { value: 0 };
    container.innerHTML = `<div class="pdf-reader__state" id="pdf-reader-state">Loading pages…</div><div class="pdf-reader__viewport" id="pdf-viewport"></div>`;
    const stateNode = container.querySelector("#pdf-reader-state");
    const viewport = container.querySelector("#pdf-viewport");
    let zoom = 1;
    let currentPage = 1;
    let totalPages = paragraphs.length || 1;
    let ready = false;

    function markReady() {
        if (ready) return;
        ready = true;
        onReady?.({ totalPages });
    }

    function renderTextFallback() {
        sentenceCounter.value = 0;
        if (!paragraphs.length) {
            stateNode.textContent = "No pages found for this book.";
            markReady();
            return;
        }
        viewport.innerHTML = paragraphs.map((paragraph, pageIndex) => `
            <article class="pdf-reader__page" data-page="${pageIndex + 1}">
                <h3 class="pdf-reader__page-number">Page ${pageIndex + 1}</h3>
                <p>${buildSentenceSpans(paragraph, sentenceCounter)}</p>
            </article>
        `).join("");
        stateNode.hidden = true;
        markReady();
    }

    async function renderPdfFile() {
        if (!pdfUrl || typeof window.pdfjsLib === "undefined") {
            renderTextFallback();
            return;
        }
        configurePdfWorker();
        const loadTimeout = window.setTimeout(() => {
            if (!ready) {
                stateNode.hidden = false;
                stateNode.textContent = "PDF is taking too long. Switched to static text view.";
                renderTextFallback();
            }
        }, 12000);
        try {
            const loadingTask = window.pdfjsLib.getDocument({
                url: pdfUrl,
                disableWorker: !window.pdfjsLib.GlobalWorkerOptions?.workerSrc,
            });
            const pdf = await loadingTask.promise;
            totalPages = pdf.numPages;
            stateNode.hidden = true;
            for (let pageNumber = 1; pageNumber <= totalPages; pageNumber += 1) {
                const page = await pdf.getPage(pageNumber);
                const canvas = document.createElement("canvas");
                const context = canvas.getContext("2d");
                const viewportInfo = page.getViewport({ scale: 1.1 });
                canvas.height = viewportInfo.height;
                canvas.width = viewportInfo.width;
                canvas.className = "pdf-reader__canvas";
                const wrapper = document.createElement("article");
                wrapper.className = "pdf-reader__page";
                wrapper.dataset.page = String(pageNumber);
                wrapper.appendChild(canvas);
                viewport.appendChild(wrapper);
                await page.render({ canvasContext: context, viewport: viewportInfo }).promise;
            }
            window.clearTimeout(loadTimeout);
            markReady();
        } catch (_error) {
            window.clearTimeout(loadTimeout);
            stateNode.hidden = false;
            stateNode.textContent = "PDF failed to load. Switched to static text view.";
            renderTextFallback();
        }
    }

    renderPdfFile();

    return {
        setPage(nextPage) {
            currentPage = Math.max(1, Math.min(totalPages, nextPage));
            const target = viewport.querySelector(`[data-page="${currentPage}"]`);
            target?.scrollIntoView({ behavior: "smooth", block: "start" });
        },
        setZoom(nextZoom) {
            zoom = Math.max(0.75, Math.min(2, nextZoom));
            viewport.style.setProperty("--pdf-zoom", String(zoom));
        },
        getTotalPages() {
            return totalPages;
        },
        isReady: () => ready,
        destroy() {
            container.innerHTML = "";
        },
    };
}
