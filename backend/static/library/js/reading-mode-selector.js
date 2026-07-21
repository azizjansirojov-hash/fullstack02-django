import { getReadingMode, setReadingMode } from "./hooks/use-reading-mode.js";

export function mountReadingModeSelector(options) {
    const { mountId, slug, onChange } = options;
    const mount = document.getElementById(mountId);
    if (!mount) return null;

    const current = getReadingMode(slug);
    mount.innerHTML = `
        <button type="button" class="reading-mode-selector__btn" data-mode="flip" aria-pressed="${current === "flip"}">Real Book</button>
        <button type="button" class="reading-mode-selector__btn" data-mode="pdf" aria-pressed="${current === "pdf"}">PDF View</button>
    `;

    function updateVisual(mode) {
        mount.querySelectorAll("[data-mode]").forEach((btn) => {
            const active = btn.dataset.mode === mode;
            btn.classList.toggle("is-active", active);
            btn.setAttribute("aria-pressed", String(active));
        });
    }

    function applyMode(mode, silent) {
        const next = setReadingMode(slug, mode);
        updateVisual(next);
        if (!silent && typeof onChange === "function") {
            onChange(next);
        }
    }

    mount.addEventListener("click", (event) => {
        const button = event.target.closest("[data-mode]");
        if (!button) return;
        applyMode(button.dataset.mode);
    });

    // Reflect saved state visually without firing onChange during initial mount
    updateVisual(current);
    return { getMode: () => getReadingMode(slug), setMode: (mode) => applyMode(mode) };
}

